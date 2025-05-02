const { SlashCommandBuilder } = require('discord.js')
module.exports = {
  data: new SlashCommandBuilder()
    .setName('stop')
    .setDescription('Stop playback and clear the queue'),
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue || !queue.playing)
      return interaction.reply({ content: '❌ Nothing to stop.', ephemeral: true })
    queue.stop()
    client.embedMessages.delete(interaction.guild.id)
    interaction.reply({ content: '⏹️ Stopped and cleared queue.', ephemeral: true })
  }
}