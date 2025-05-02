module.exports = {
  customId: 'stop',
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue) return interaction.reply({ content: '❌ Nothing to stop.', ephemeral: true })
    queue.stop()
    client.embedMessages.delete(interaction.guild.id)
    await interaction.update({ content: '⏹️ Playback stopped.', embeds: [], components: [] })
  }
}