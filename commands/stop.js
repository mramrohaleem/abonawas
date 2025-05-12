const { SlashCommandBuilder } = require('discord.js');
const audioService = require('../services/audioService');
const logger = require('../utils/logger');

module.exports = {
  data: new SlashCommandBuilder().setName('stop').setDescription('Stop playback and clear queue'),
  async execute(interaction) {
    const traceId = logger.trace();
    try {
      await audioService.stop(interaction.guildId, traceId);
      await interaction.reply({ content: '⏹️ Stopped and queue cleared', ephemeral: true });
    } catch (err) {
      logger.error('Stop failed', { traceId, err });
      await interaction.reply({ content: `Error \`CMD_STOP_FAILED\`: ${err.message}`, ephemeral: true });
    }
  },
};
