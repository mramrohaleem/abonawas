module.exports = {
  customId: 'stop',
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing)
      return interaction.reply({ content:'❌ Nothing to stop.', ephemeral:true })
    q.stop()
    client.embedMessages.delete(interaction.guild.id)
    await interaction.update({ content:'⏹️ Playback stopped.', embeds:[], components:[] })
  }
}