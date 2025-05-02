// src/commands/play.js
const {
  SlashCommandBuilder,
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require('discord.js')
const { QueryType } = require('discord-player')

module.exports = {
  data: new SlashCommandBuilder()
    .setName('play')
    .setDescription('Play a song from YouTube (link or search)')
    .addStringOption(opt =>
      opt
        .setName('query')
        .setDescription('YouTube URL or search keywords')
        .setRequired(true)
    ),
  async execute(interaction, client) {
    const query = interaction.options.getString('query')
    const voiceChannel = interaction.member.voice.channel
    if (!voiceChannel) {
      return interaction.reply({
        content: '❌ You need to join a voice channel first!',
        ephemeral: true
      })
    }

    await interaction.deferReply()

    // 1. إنشاء الـ Queue أو استعادته
    const queue = client.player.createQueue(interaction.guild, {
      metadata: { channel: interaction.channel }
    })

    // 2. ربط البوت بالقناة الصوتية
    try {
      if (!queue.connection) await queue.connect(voiceChannel)
    } catch (err) {
      queue.destroy()
      return interaction.followUp({
        content: '❌ Could not join your voice channel.',
        ephemeral: true
      })
    }

    // 3. البحث عن المقاطع
    const searchResult = await client.player.search(query, {
      requestedBy: interaction.user,
      searchEngine: QueryType.AUTO
    })

    if (!searchResult || !searchResult.tracks.length) {
      return interaction.followUp({
        content: '❌ No results found.',
        ephemeral: true
      })
    }

    // 4. إضافة أو اختيار أول مقطع
    const track = searchResult.tracks[0]
    queue.addTrack(track)

    // 5. تشغيل إذا لم يكن هناك تشغيل جاري
    if (!queue.playing) await queue.play()

    // 6. إعداد أزرار التحكم
    const controls = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('previous')
        .setEmoji('⏮️')
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId('play_pause')
        .setEmoji('⏯️')
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId('skip')
        .setEmoji('⏭️')
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId('stop')
        .setEmoji('⏹️')
        .setStyle(ButtonStyle.Danger),
      new ButtonBuilder()
        .setCustomId('loop')
        .setEmoji('🔄')
        .setStyle(ButtonStyle.Secondary),
      new ButtonBuilder()
        .setCustomId('destroy')
        .setEmoji('❌')
        .setStyle(ButtonStyle.Danger)
    )

    // 7. إرسال Embed "Now Playing"
    const embed = new EmbedBuilder()
      .setTitle('Now Playing')
      .setDescription(`[${track.title}](${track.url})`)
      .setThumbnail(track.thumbnail)
      .addFields(
        { name: 'Duration', value: track.duration, inline: true },
        {
          name: 'Requested by',
          value: `<@${track.requestedBy.id}>`,
          inline: true
        }
      )
      .setColor('Blue')

    const msg = await interaction.followUp({
      embeds: [embed],
      components: [controls]
    })

    // 8. احفظ رسالة الـ Embed للتحديث لاحقاً
    client.embedMessages.set(interaction.guild.id, msg)

    // 9. حدث عند بدء تشغيل مقطع جديد لتحديث الـ Embed
    client.player.on('trackStart', (queue, playingTrack) => {
      if (queue.metadata.channel.id !== interaction.channel.id) return

      const nowEmbed = new EmbedBuilder()
        .setTitle('Now Playing')
        .setDescription(`[${playingTrack.title}](${playingTrack.url})`)
        .setThumbnail(playingTrack.thumbnail)
        .addFields(
          { name: 'Duration', value: playingTrack.duration, inline: true },
          {
            name: 'Requested by',
            value: `<@${playingTrack.requestedBy.id}>`,
            inline: true
          }
        )
        .setColor('Blue')

      const embedMsg = client.embedMessages.get(interaction.guild.id)
      if (embedMsg) embedMsg.edit({ embeds: [nowEmbed] }).catch(() => {})
    })

    // 10. حدث عند انتهاء القائمة
    client.player.on('queueEnd', queue => {
      queue.metadata.channel.send('✅ Queue has ended.')
      client.embedMessages.delete(interaction.guild.id)
    })
  }
}
