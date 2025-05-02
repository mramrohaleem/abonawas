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
    .setDescription('Play from YouTube (link or search)')
    .addStringOption(opt =>
      opt.setName('query')
        .setDescription('YouTube URL or keywords')
        .setRequired(true)
    ),
  async execute(interaction, client) {
    const query = interaction.options.getString('query')
    const vc = interaction.member.voice.channel
    if (!vc) return interaction.reply({ content: '❌ Join a voice channel first!', ephemeral: true })

    await interaction.deferReply()
    const queue = client.player.createQueue(interaction.guild, {
      metadata: { channel: interaction.channel }
    })
    try {
      if (!queue.connection) await queue.connect(vc)
    } catch {
      queue.destroy()
      return interaction.followUp({ content: '❌ Could not join voice channel.', ephemeral: true })
    }

    const track = await queue.play(query, {
      requestedBy: interaction.user,
      searchEngine: QueryType.AUTO
    }).catch(() => null)

    if (!track) return interaction.followUp({ content: '❌ No results found.', ephemeral: true })

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('previous').setEmoji('⏮️').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('play_pause').setEmoji('⏯️').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('skip').setEmoji('⏭️').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('stop').setEmoji('⏹️').setStyle(ButtonStyle.Danger),
      new ButtonBuilder().setCustomId('loop').setEmoji('🔄').setStyle(ButtonStyle.Secondary),
      new ButtonBuilder().setCustomId('destroy').setEmoji('❌').setStyle(ButtonStyle.Danger)
    )

    const embed = new EmbedBuilder()
      .setTitle('Now Playing')
      .setDescription(`[${track.title}](${track.url})`)
      .setThumbnail(track.thumbnail)
      .addFields(
        { name: 'Duration', value: track.duration, inline: true },
        { name: 'Requested by', value: `<@${track.requestedBy.id}>`, inline: true }
      )
      .setColor('Blue')

    const msg = await interaction.followUp({ embeds: [embed], components: [row] })
    client.embedMessages.set(interaction.guild.id, msg)

    queue.events.on('playerStart', (_, playing) => {
      const now = new EmbedBuilder()
        .setTitle('Now Playing')
        .setDescription(`[${playing.title}](${playing.url})`)
        .setThumbnail(playing.thumbnail)
        .addFields(
          { name: 'Duration', value: playing.duration, inline: true },
          { name: 'Requested by', value: `<@${playing.requestedBy.id}>`, inline: true }
        )
        .setColor('Blue')
      const eMsg = client.embedMessages.get(interaction.guild.id)
      if (eMsg) eMsg.edit({ embeds: [now] }).catch(() => {})
    })

    queue.events.on('queueEnd', q => {
      q.metadata.channel.send('✅ Queue has ended.')
      client.embedMessages.delete(interaction.guild.id)
    })
  }
}