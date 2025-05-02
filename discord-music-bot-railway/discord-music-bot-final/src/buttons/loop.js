const { RepeatMode } = require('discord-player')
module.exports = {
  customId: 'loop',
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue) return interaction.reply({ content: '❌ No track playing.', ephemeral: true })
    const current = queue.repeatMode
    const next = current === RepeatMode.OFF ? RepeatMode.TRACK
      : current === RepeatMode.TRACK ? RepeatMode.QUEUE
      : RepeatMode.OFF
    queue.setRepeatMode(next)
    await interaction.reply({ content: `🔁 Loop mode: **${['Off','Track','Queue'][next]}**`, ephemeral: true })
  }
}