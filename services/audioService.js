const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');
const { pipeline } = require('stream');
const { promisify } = require('util');
const { v4: uuidv4 } = require('uuid');
const {
  createAudioPlayer,
  createAudioResource,
  joinVoiceChannel,
  AudioPlayerStatus,
  VoiceConnectionStatus,
  NoSubscriberBehavior
} = require('@discordjs/voice');
const { EmbedBuilder } = require('discord.js');
const logger = require('../utils/logger');

const streamPipeline = promisify(pipeline);
const cacheDir = process.env.CACHE_DIR || path.join(__dirname, '..', 'cache');
const maxCacheFiles = 20;
const maxCacheSize = 100 * 1024 * 1024;
const idleTimeout = 60 * 1000;
const cleanupInterval = 10 * 60 * 1000;

const guildStates = new Map();

if (!fs.existsSync(cacheDir)) fs.mkdirSync(cacheDir, { recursive: true });
setInterval(cleanupCache, cleanupInterval);

function trace() { return uuidv4().split('-')[0]; }

async function enqueue(interaction, input, traceId) {
  const guildId = interaction.guildId;
  let state = guildStates.get(guildId);
  if (!state) {
    state = { queue: [], connection: null, player: null, current: null };
    guildStates.set(guildId, state);
  }
  const memberVC = interaction.member.voice.channel;
  if (!memberVC) throw new Error('You must join a voice channel');
  if (!state.connection) {
    state.connection = joinVoiceChannel({
      channelId: memberVC.id,
      guildId,
      adapterCreator: interaction.guild.voiceAdapterCreator
    });
    state.connection.on('stateChange', (oldS, newS) => {
      logger.info('Connection state', { traceId, from: oldS.status, to: newS.status });
      if (newS.status === VoiceConnectionStatus.Disconnected) {
        setTimeout(() => state.connection.rejoin(), 5000);
      }
    });
    state.player = createAudioPlayer({ behaviors: { noSubscriber: NoSubscriberBehavior.Play } });
    state.connection.subscribe(state.player);
    state.player.on('stateChange', (oldP, newP) => {
      if (newP.status === AudioPlayerStatus.Idle && state.queue.length) {
        playNext(guildId, trace());
      }
    });
  }
  let url = input;
  if (/^\d+:\d+$/.test(input)) {
    const [s, a] = input.split(':');
    url = `https://api.alquran.cloud/v1/ayah/${s}:${a}/ar.alafasy?audio`;
  }
  const fileName = `${uuidv4()}.mp3`;
  const filePath = path.join(cacheDir, fileName);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Fetch failed ${url}`);
  await streamPipeline(res.body, fs.createWriteStream(filePath));
  state.queue.push({ title: input, path: filePath });
  if (state.player.state.status !== AudioPlayerStatus.Playing) {
    playNext(guildId, traceId);
  }
  return state.queue;
}

function playNext(guildId, traceId) {
  const state = guildStates.get(guildId);
  if (!state || !state.queue.length) return;
  const track = state.queue.shift();
  const resource = createAudioResource(track.path, { inlineVolume: true });
  state.player.play(resource);
  state.current = track;
}

async function skip(guildId) {
  const state = guildStates.get(guildId);
  if (!state) throw new Error('No queue');
  state.player.stop();
}

async function pause(guildId) {
  const state = guildStates.get(guildId);
  if (!state) throw new Error('Nothing to pause');
  state.player.pause();
}

async function resume(guildId) {
  const state = guildStates.get(guildId);
  if (!state) throw new Error('Nothing to resume');
  state.player.unpause();
}

async function stop(guildId) {
  const state = guildStates.get(guildId);
  if (!state) throw new Error('Nothing to stop');
  state.queue = [];
  state.player.stop();
  state.connection.destroy();
  guildStates.delete(guildId);
}

function getQueue(guildId) {
  const state = guildStates.get(guildId);
  return state ? state.queue : [];
}

function getQueueEmbed(queue) {
  return new EmbedBuilder()
    .setTitle('Queue')
    .setDescription(queue.map((t,i) => `${i+1}. ${t.title}`).join('\n') || 'Empty')
    .setColor(0x00AE86);
}

async function handleVoiceStateUpdate(oldState, newState) {
  const guildId = oldState.guild.id;
  const state = guildStates.get(guildId);
  if (!state || !state.connection) return;
  const vcId = state.connection.joinConfig.channelId;
  const voiceChannel = oldState.guild.channels.cache.get(vcId);
  if (voiceChannel.members.filter(m => !m.user.bot).size === 0) {
    setTimeout(() => {
      const ch = oldState.guild.channels.cache.get(vcId);
      if (ch.members.filter(m => !m.user.bot).size === 0) {
        state.connection.destroy();
        guildStates.delete(guildId);
        logger.info('Auto-disconnected', { trace: trace() });
      }
    }, idleTimeout);
  }
}

function cleanupCache() {
  const files = fs.readdirSync(cacheDir).map(f => {
    const p = path.join(cacheDir, f);
    const { mtimeMs, size } = fs.statSync(p);
    return { file: f, path: p, mtime: mtimeMs, size };
  });
  let total = files.reduce((acc, f) => acc + f.size, 0);
  files.sort((a,b) => a.mtime - b.mtime);
  while (files.length > maxCacheFiles || total > maxCacheSize) {
    const f = files.shift();
    try { fs.unlinkSync(f.path); total -= f.size; } catch {}
  }
}

module.exports = { enqueue, skip, pause, resume, stop, getQueue, getQueueEmbed, handleVoiceStateUpdate };
