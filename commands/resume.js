const { SlashCommandBuilder } = require('discord.js');
const audioService = require('../services/audioService');
const logger = require('../utils/logger');

module.exports = {
  data: new SlashCommandBuilder().setName('resume').setDescription('Resume playback'),
  async execute(interaction) {
    const traceId = logger.trace();
    try {
      await audioService.resume(interaction.guildId, traceId);
      await interaction.reply({ content: '▶️ Resumed', ephemeral: true });
    } catch (err) {
      logger.error('Resume failed', { traceId, err });
      await interaction.reply({ content: `Error \`CMD_RESUME_FAILED\`: ${err.message}`, ephemeral: true });
    }
  },
};
