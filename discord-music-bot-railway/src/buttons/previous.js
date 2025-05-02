module.exports = {
  customId: 'previous',
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing || !q.history.previous)
      return interaction.reply({ content:'❌ No previous track.', ephemeral:true })
    q.back()
    await interaction.update({})
  }
}