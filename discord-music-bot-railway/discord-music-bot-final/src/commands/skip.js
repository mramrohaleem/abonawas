const { SlashCommandBuilder } = require('discord.js')
module.exports = {
  data: new SlashCommandBuilder()
    .setName('skip')
    .setDescription('Skip the current track'),
  async execute(interaction, client) {
    const queue = client.player.getQueue(interaction.guild)
    if (!queue || !queue.playing)
      return interaction.reply({ content: '❌ No track to skip.', ephemeral: true })
    queue.skip()
    interaction.reply({ content: '⏭️ Skipped.', ephemeral: true })
  }
}