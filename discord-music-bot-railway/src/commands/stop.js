const { SlashCommandBuilder } = require('discord.js')
module.exports = {
  data: new SlashCommandBuilder().setName('stop').setDescription('Stop playback & clear queue'),
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing)
      return interaction.reply({ content:'❌ Nothing to stop.', ephemeral:true })
    q.stop()
    client.embedMessages.delete(interaction.guild.id)
    interaction.reply({ content:'⏹️ Stopped and cleared.', ephemeral:true })
  }
}