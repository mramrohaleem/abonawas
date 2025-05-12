const { SlashCommandBuilder } = require('discord.js');
const audioService = require('../services/audioService');
const logger = require('../utils/logger');

module.exports = {
  data: new SlashCommandBuilder()
    .setName('play')
    .setDescription('Enqueue and play a track (URL or Surah:Ayah)')
    .addStringOption(o => o.setName('input').setDescription('URL or Surah:Ayah').setRequired(true)),
  async execute(interaction) {
    const traceId = logger.trace();
    const input = interaction.options.getString('input');
    await interaction.deferReply();
    try {
      const queue = await audioService.enqueue(interaction, input, traceId);
      await interaction.editReply({ embeds: [audioService.getQueueEmbed(queue)] });
    } catch (err) {
      logger.error('Play failed', { traceId, err });
      await interaction.editReply({ content: `Error \`CMD_PLAY_FAILED\`: ${err.message}`, ephemeral: true });
    }
  },
};
