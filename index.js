import { Client, GatewayIntentBits, Partials, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, REST, Routes, Events } from 'discord.js';
import { joinVoiceChannel, createAudioPlayer, createAudioResource, AudioPlayerStatus, VoiceConnectionStatus } from '@discordjs/voice';
import fetch from 'node-fetch';
import { Readable } from 'stream';
import dotenv from 'dotenv';
import sodium from 'libsodium-wrappers';

dotenv.config();
await sodium.ready;

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildVoiceStates
    ],
    partials: [Partials.Channel]
});

const token = process.env.DISCORD_TOKEN;
const queues = new Map();

client.once('ready', () => {
    console.log(`✅ Logged in as ${client.user.tag}`);
});

const commands = [
    {
        name: 'play',
        description: 'شغّل ملف mp3 من رابط مباشر',
        options: [{
            name: 'url',
            type: 3,
            description: 'رابط mp3 مباشر',
            required: true
        }]
    },
    {
        name: 'queue',
        description: 'عرض الطابور الحالي'
    }
];

client.on(Events.InteractionCreate, async interaction => {
    if (!interaction.isChatInputCommand() && !interaction.isButton()) return;

    const guildId = interaction.guildId;
    const member = interaction.member;

    if (interaction.isChatInputCommand()) {
        if (interaction.commandName === 'play') {
            const url = interaction.options.getString('url');
            if (!url.endsWith('.mp3')) return interaction.reply({ content: '❌ يجب أن يكون الرابط مباشرًا وينتهي بـ `.mp3`', ephemeral: true });

            if (!member.voice.channel) return interaction.reply({ content: '❗ يجب أن تنضم إلى قناة صوتية أولًا.', ephemeral: true });

            let q = queues.get(guildId);
            if (!q) {
                const connection = joinVoiceChannel({
                    channelId: member.voice.channel.id,
                    guildId: guildId,
                    adapterCreator: interaction.guild.voiceAdapterCreator
                });

                const player = createAudioPlayer();
                connection.subscribe(player);
                q = { queue: [], player, connection, controlMessage: null, timeout: null };
                queues.set(guildId, q);

                connection.on(VoiceConnectionStatus.Disconnected, () => {
                    setTimeout(() => {
                        if (connection.state.status === VoiceConnectionStatus.Disconnected) {
                            connection.destroy();
                            queues.delete(guildId);
                            console.log('👋 Connection destroyed');
                        }
                    }, 1000);
                });

                player.on(AudioPlayerStatus.Idle, () => {
                    console.log('🔁 Player entered IDLE mode. Skipping to next track if available.');
                    q.queue.shift();
                    if (q.queue.length > 0) {
                        playTrack(guildId);
                    } else {
                        updateControl(guildId);
                        q.timeout = setTimeout(() => {
                            if (q.connection && q.connection.joinConfig.channelId) {
                                const channel = client.channels.cache.get(q.connection.joinConfig.channelId);
                                if (channel && channel.members.size === 1) {
                                    q.connection.destroy();
                                    queues.delete(guildId);
                                    console.log('⏹️ Left due to inactivity.');
                                }
                            }
                        }, 60000);
                    }
                });

                player.on('error', err => {
                    console.error('❌ Audio Player Error:', err);
                });
            }

            q.queue.push({ url });
            interaction.reply({ content: `📥 تمت إضافة الرابط إلى الطابور.`, ephemeral: true });
            updateControl(guildId);

            if (q.player.state.status === AudioPlayerStatus.Idle) {
                playTrack(guildId);
            }

        } else if (interaction.commandName === 'queue') {
            const q = queues.get(guildId);
            if (!q || q.queue.length === 0) return interaction.reply({ content: '📭 الطابور فارغ حالياً.', ephemeral: true });

            const embed = new EmbedBuilder()
                .setTitle('🎶 الطابور الحالي')
                .setDescription(q.queue.map((t, i) => `${i + 1}. ${t.url}`).join('\n'))
                .setColor('Blue');

            interaction.reply({ embeds: [embed], ephemeral: true });
        }
    }

    if (interaction.isButton()) {
        const q = queues.get(guildId);
        if (!q) return;

        switch (interaction.customId) {
            case 'pause':
                q.player.pause();
                break;
            case 'resume':
                q.player.unpause();
                break;
            case 'skip':
                q.player.stop();
                break;
            case 'stop':
                q.player.stop();
                q.connection.destroy();
                queues.delete(guildId);
                break;
        }
        await interaction.deferUpdate();
        updateControl(guildId);
    }
});

async function playTrack(guildId) {
    const q = queues.get(guildId);
    if (!q || q.queue.length === 0) return;

    clearTimeout(q.timeout);

    const track = q.queue[0];
    try {
        const res = await fetch(track.url, {
            headers: {
                'User-Agent': 'Mozilla/5.0',
                'Connection': 'keep-alive'
            }
        });

        if (!res.ok) {
            console.error(`❌ HTTP error ${res.status}: ${res.statusText}`);
            return;
        }

        const arrayBuffer = await res.arrayBuffer();
        const buffer = Buffer.from(arrayBuffer);
        const stream = Readable.from(buffer);

        const resource = createAudioResource(stream);
        q.player.play(resource);
        console.log(`▶️ Now playing from buffer: ${track.url}`);
        updateControl(guildId);
    } catch (err) {
        console.error('❌ فشل في تشغيل الرابط (buffered):', err);
    }
}

async function updateControl(guildId) {
    const q = queues.get(guildId);
    if (!q) return;

    const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId('pause').setEmoji('⏸️').setStyle(ButtonStyle.Secondary).setDisabled(q.player.state.status !== AudioPlayerStatus.Playing),
        new ButtonBuilder().setCustomId('resume').setEmoji('▶️').setStyle(ButtonStyle.Secondary).setDisabled(q.player.state.status !== AudioPlayerStatus.Paused),
        new ButtonBuilder().setCustomId('skip').setEmoji('⏭️').setStyle(ButtonStyle.Secondary).setDisabled(q.queue.length < 2),
        new ButtonBuilder().setCustomId('stop').setEmoji('⏹️').setStyle(ButtonStyle.Danger)
    );

    const embed = new EmbedBuilder()
        .setTitle('🎧 يتم التشغيل الآن')
        .setDescription(q.queue[0] ? q.queue[0].url : 'لا يوجد')
        .setColor('Green');

    try {
        if (!q.controlMessage) {
            const channel = client.channels.cache.find(c => c.isTextBased() && c.guildId === guildId);
            if (!channel) return;
            q.controlMessage = await channel.send({ embeds: [embed], components: [row] });
        } else {
            await q.controlMessage.edit({ embeds: [embed], components: [row] });
        }
    } catch (err) {
        console.error('🔧 Error updating control message:', err);
    }
}

(async () => {
    const rest = new REST({ version: '10' }).setToken(token);
    try {
        console.log('🔁 Registering slash commands...');
        await rest.put(Routes.applicationCommands((await client.application?.id) || (await client.login(token), client.user.id)), { body: commands });
        console.log('✅ Commands registered.');
    } catch (err) {
        console.error('❌ Failed to register commands:', err);
    }
})();

client.login(token);

