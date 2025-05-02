const { SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js')
const { QueryType } = require('discord-player')

module.exports = {
  data: new SlashCommandBuilder()
    .setName('play')
    .setDescription('Play a song from YouTube')
    .addStringOption(o => o.setName('query').setDescription('Search terms or URL').setRequired(true)),
  async execute(interaction, client) {
    const query = interaction.options.getString('query')
    const vc = interaction.member.voice.channel
    if (!vc) return interaction.reply({ content: 'Join a voice channel first!', ephemeral: true })

    await interaction.deferReply()
    const queue = client.player.createQueue(interaction.guild, { metadata: { channel: interaction.channel } })
    try { if (!queue.connection) await queue.connect(vc) }
    catch { queue.destroy(); return interaction.followUp('❌ Could not join voice channel.') }

    const track = await queue.play(query, {
      requestedBy: interaction.user,
      searchEngine: QueryType.AUTO
    }).catch(() => null)
    if (!track) return interaction.followUp('❌ No results found.')

    const row = new ActionRowBuilder()
      .addComponents(
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
      ).setColor('Blue')

    const msg = await interaction.followUp({ embeds: [embed], components: [row] })
    client.embedMessages.set(interaction.guild.id, msg)

    const update = (_, t) => {
      const e = new EmbedBuilder()
        .setTitle('Now Playing')
        .setDescription(`[${t.title}](${t.url})`)
        .setThumbnail(t.thumbnail)
        .addFields(
          { name: 'Duration', value: t.duration, inline: true },
          { name: 'Requested by', value: `<@${t.requestedBy.id}>`, inline: true }
        ).setColor('Blue')
      client.embedMessages.get(interaction.guild.id)?.edit({ embeds: [e] }).catch(() => {})
    }
    queue.events.on('playerStart', update)
    queue.events.on('queueEnd', () => {
      interaction.channel.send('✅ Queue has ended.')
      client.embedMessages.delete(interaction.guild.id)
    })
  }
}