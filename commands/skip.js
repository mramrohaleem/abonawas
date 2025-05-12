const { SlashCommandBuilder } = require('discord.js');
const audioService = require('../services/audioService');
const logger = require('../utils/logger');

module.exports = {
  data: new SlashCommandBuilder().setName('skip').setDescription('Skip to next track'),
  async execute(interaction) {
    const traceId = logger.trace();
    try {
      await audioService.skip(interaction.guildId, traceId);
      await interaction.reply({ content: '⏭️ Skipped', ephemeral: true });
    } catch (err) {
      logger.error('Skip failed', { traceId, err });
      await interaction.reply({ content: `Error \`CMD_SKIP_FAILED\`: ${err.message}`, ephemeral: true });
    }
  },
};
