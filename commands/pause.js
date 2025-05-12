const { SlashCommandBuilder } = require('discord.js');
const audioService = require('../services/audioService');
const logger = require('../utils/logger');

module.exports = {
  data: new SlashCommandBuilder().setName('pause').setDescription('Pause playback'),
  async execute(interaction) {
    const traceId = logger.trace();
    try {
      await audioService.pause(interaction.guildId, traceId);
      await interaction.reply({ content: '⏸️ Paused', ephemeral: true });
    } catch (err) {
      logger.error('Pause failed', { traceId, err });
      await interaction.reply({ content: `Error \`CMD_PAUSE_FAILED\`: ${err.message}`, ephemeral: true });
    }
  },
};
