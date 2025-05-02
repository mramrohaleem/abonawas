module.exports = {
  customId: 'skip',
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing)
      return interaction.reply({ content:'❌ No track to skip.', ephemeral:true })
    q.skip()
    await interaction.update({})
  }
}