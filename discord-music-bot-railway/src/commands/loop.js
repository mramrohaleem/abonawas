const { SlashCommandBuilder } = require('discord.js')
const { RepeatMode } = require('discord-player')
module.exports = {
  data: new SlashCommandBuilder().setName('loop').setDescription('Toggle loop mode'),
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing)
      return interaction.reply({ content:'❌ No track playing.', ephemeral:true })

    const next = q.repeatMode === RepeatMode.OFF
      ? RepeatMode.TRACK
      : q.repeatMode === RepeatMode.TRACK
        ? RepeatMode.QUEUE
        : RepeatMode.OFF

    q.setRepeatMode(next)
    const modes = ['Off','Track','Queue']
    interaction.reply({ content:`🔁 Loop: **${modes[next]}**`, ephemeral:true })
  }
}