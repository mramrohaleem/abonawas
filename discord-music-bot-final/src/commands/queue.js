const { SlashCommandBuilder, EmbedBuilder } = require('discord.js')

module.exports = {
  data: new SlashCommandBuilder()
    .setName('queue')
    .setDescription('Show the current song queue'),
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue || !queue.playing)
      return interaction.reply({ content: '❌ No songs in queue.', ephemeral: true })

    const list = queue.tracks
      .map((t,i) => `**${i+1}.** [${t.title}](${t.url}) — <@${t.requestedBy.id}>`)
      .slice(0,10)
      .join('\n')

    const embed = new EmbedBuilder()
      .setTitle('Server Queue')
      .setDescription(list || 'No more songs')
      .setFooter({ text: `Now playing: ${queue.current.title}` })
      .setColor('Blue')

    interaction.reply({ embeds: [embed] })
  }
}