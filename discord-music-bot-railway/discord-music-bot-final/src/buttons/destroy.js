module.exports = {
  customId: 'destroy',
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (queue) queue.destroy()
    client.embedMessages.delete(interaction.guild.id)
    await interaction.update({ content: '❌ Player destroyed.', embeds: [], components: [] })
  }
}