const { SlashCommandBuilder } = require('discord.js')
const { RepeatMode } = require('discord-player')
module.exports = {
  data: new SlashCommandBuilder()
    .setName('loop')
    .setDescription('Toggle loop mode'),
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue || !queue.playing)
      return interaction.reply({ content: '❌ No track playing.', ephemeral: true })
    const current = queue.repeatMode
    const next = current === RepeatMode.OFF ? RepeatMode.TRACK
      : current === RepeatMode.TRACK ? RepeatMode.QUEUE
      : RepeatMode.OFF
    queue.setRepeatMode(next)
    interaction.reply({ content: `🔁 Loop mode: **${['Off','Track','Queue'][next]}**`, ephemeral: true })
  }
}