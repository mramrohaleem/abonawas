const { SlashCommandBuilder } = require('discord.js')
module.exports = {
  data: new SlashCommandBuilder()
    .setName('previous')
    .setDescription('Play previous track'),
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue || !queue.history.previous)
      return interaction.reply({ content: '❌ No previous track.', ephemeral: true })
    queue.back()
    interaction.reply({ content: '⏮️ Playing previous track.', ephemeral: true })
  }
}