module.exports = {
  customId: 'play_pause',
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue) return interaction.reply({ content: '❌ Nothing playing.', ephemeral: true })
    queue.connection.paused ? queue.setPaused(false) : queue.setPaused(true)
    await interaction.update({ embeds: interaction.message.embeds, components: interaction.message.components })
  }
}