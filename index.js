import { Client, GatewayIntentBits, Partials, Collection, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, Events, REST, Routes } from 'discord.js';
import { joinVoiceChannel, createAudioPlayer, createAudioResource, AudioPlayerStatus, getVoiceConnection, VoiceConnectionStatus } from '@discordjs/voice';
import play from 'play-dl';
import dotenv from 'dotenv';
dotenv.config();

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildVoiceStates,
    ],
    partials: [Partials.Channel]
});

const token = process.env.DISCORD_TOKEN;
const queues = new Map(); // guildId => { queue: [], player, connection, controlMessage, timeout }

client.once('ready', () => {
    console.log(`✅ Logged in as ${client.user.tag}`);
});

const commands = [
    {
        name: 'play',
        description: 'شغّل تلاوة من رابط SoundCloud',
        options: [{
            name: 'url',
            type: 3,
            description: 'رابط SoundCloud',
            required: true
        }]
    },
    {
        name: 'queue',
        description: 'عرض طابور التشغيل الحالي'
    }
];

client.on(Events.InteractionCreate, async interaction => {
    if (!interaction.isChatInputCommand() && !interaction.isButton()) return;

    const guildId = interaction.guildId;
    const member = interaction.member;

    if (interaction.isChatInputCommand()) {
        if (interaction.commandName === 'play') {
            const url = interaction.options.getString('url');

            let info;
            try {
                info = await play.soundcloud(url);
            } catch (err) {
                console.error('❌ Error fetching track:', err);
                return interaction.reply({ content: 'رابط غير صالح أو حدث خطأ في التحميل.', ephemeral: true });
            }

            if (!member.voice.channel) return interaction.reply({ content: 'يجب أن تكون في قناة صوتية أولاً!', ephemeral: true });

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

                connection.on(VoiceConnectionStatus.Disconnected, async () => {
                    setTimeout(() => {
                        if (connection.state.status === VoiceConnectionStatus.Disconnected) {
                            connection.destroy();
                            queues.delete(guildId);
                            console.log('👋 Connection destroyed (disconnected)');
                        }
                    }, 1000);
                });

                player.on(AudioPlayerStatus.Idle, () => {
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
            }

            q.queue.push({ url, title: info.name });
            interaction.reply({ content: `📥 تمت إضافة: **${info.name}**`, ephemeral: true });

            if (q.player.state.status === AudioPlayerStatus.Idle) {
                playTrack(guildId);
            }

        } else if (interaction.commandName === 'queue') {
            const q = queues.get(guildId);
            if (!q || q.queue.length === 0) return interaction.reply({ content: '📭 لا توجد تلاوات في الطابور.', ephemeral: true });

            const embed = new EmbedBuilder()
                .setTitle('🎶 قائمة التشغيل')
                .setDescription(q.queue.map((t, i) => `${i + 1}. ${t.title}`).join('\n'))
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
    const stream = await play.stream(track.url);
    const resource = createAudioResource(stream.stream, { inputType: stream.type });
    q.player.play(resource);

    updateControl(guildId);
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
        .setDescription(q.queue[0] ? q.queue[0].title : 'لا يوجد')
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
