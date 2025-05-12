const audioService = require('../services/audioService');
const logger = require('../utils/logger');

module.exports = {
  name: 'voiceStateUpdate',
  async execute(oldState, newState) {
    try {
      await audioService.handleVoiceStateUpdate(oldState, newState);
    } catch (err) {
      logger.error('VoiceStateUpdate error', { err });
    }
  },
};
