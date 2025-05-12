const { SlashCommandBuilder } = require('discord.js');
const audioService = require('../services/audioService');
const logger = require('../utils/logger');

module.exports = {
  data: new SlashCommandBuilder().setName('queue').setDescription('Show current queue'),
  async execute(interaction) {
    const traceId = logger.trace();
    try {
      const queue = audioService.getQueue(interaction.guildId);
      await interaction.reply({ embeds: [audioService.getQueueEmbed(queue)] });
    } catch (err) {
      logger.error('Queue failed', { traceId, err });
      await interaction.reply({ content: `Error \`CMD_QUEUE_FAILED\`: ${err.message}`, ephemeral: true });
    }
  },
};
