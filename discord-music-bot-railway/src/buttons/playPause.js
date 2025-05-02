module.exports = {
  customId: 'play_pause',
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing)
      return interaction.reply({ content:'❌ Nothing playing.', ephemeral:true })
    q.connection.paused ? q.setPaused(false) : q.setPaused(true)
    await interaction.update({ embeds: interaction.message.embeds, components: interaction.message.components })
  }
}