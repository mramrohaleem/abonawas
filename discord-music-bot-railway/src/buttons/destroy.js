module.exports = {
  customId: 'destroy',
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (q) q.destroy()
    client.embedMessages.delete(interaction.guild.id)
    await interaction.update({ content:'❌ Player destroyed.', embeds:[], components:[] })
  }
}