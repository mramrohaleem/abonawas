const { RepeatMode } = require('discord-player')
module.exports = {
  customId: 'loop',
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing)
      return interaction.reply({ content:'❌ No track playing.', ephemeral:true })
    const next = q.repeatMode === RepeatMode.OFF ? RepeatMode.TRACK : q.repeatMode === RepeatMode.TRACK ? RepeatMode.QUEUE : RepeatMode.OFF
    q.setRepeatMode(next)
    await interaction.reply({ content:`🔁 Loop: **${['Off','Track','Queue'][next]}**`, ephemeral:true })
  }
}