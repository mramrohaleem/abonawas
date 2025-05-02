module.exports = {
  customId: 'previous',
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue || !queue.history.previous) return interaction.reply({ content: '❌ No previous track.', ephemeral: true })
    queue.back()
    await interaction.update({})
  }
}