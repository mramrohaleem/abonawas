const { SlashCommandBuilder } = require('discord.js')
module.exports = {
  data: new SlashCommandBuilder().setName('skip').setDescription('Skip the current track'),
  async execute(interaction, client) {
    const q = client.player.getQueue(interaction.guild)
    if (!q || !q.playing)
      return interaction.reply({ content:'❌ No track to skip.', ephemeral:true })
    q.skip()
    interaction.reply({ content:'⏭️ Skipped.', ephemeral:true })
  }
}