require('dotenv').config();
const fs = require('fs');
const path = require('path');
const { REST, Routes } = require('discord.js');
const logger = require('./utils/logger');

const commands = [];
for (const file of fs.readdirSync(path.join(__dirname, 'commands')).filter(f => f.endsWith('.js'))) {
  const cmd = require(`./commands/${file}`);
  commands.push(cmd.data.toJSON());
}

const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
(async () => {
  try {
    logger.info('Refreshing application (/) commands');
    await rest.put(
      Routes.applicationCommands(process.env.CLIENT_ID),
      { body: commands },
    );
    logger.info('Commands reloaded');
  } catch (err) {
    logger.error('Command registration failed', { err });
  }
})();
