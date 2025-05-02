module.exports = {
  customId: 'skip',
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue) return interaction.reply({ content: '❌ No track to skip.', ephemeral: true })
    queue.skip()
    await interaction.update({})
  }
}