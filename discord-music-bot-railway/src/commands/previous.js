const { SlashCommandBuilder } = require('discord.js')
module.exports = {
  data: new SlashCommandBuilder().setName('previous').setDescription('Play previous track'),
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing || !q.history.previous)
      return interaction.reply({ content:'❌ No previous track.', ephemeral:true })
    q.back()
    interaction.reply({ content:'⏮️ Playing previous.', ephemeral:true })
  }
}