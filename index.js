require('dotenv').config();
const fs = require('fs');
const path = require('path');
const { Client, Collection, GatewayIntentBits } = require('discord.js');
const logger = require('./utils/logger');

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
client.commands = new Collection();

for (const file of fs.readdirSync(path.join(__dirname, 'commands')).filter(f => f.endsWith('.js'))) {
  const command = require(`./commands/${file}`);
  client.commands.set(command.data.name, command);
}

for (const file of fs.readdirSync(path.join(__dirname, 'events')).filter(f => f.endsWith('.js'))) {
  const evt = require(`./events/${file}`);
  if (evt.once) client.once(evt.name, (...args) => evt.execute(client, ...args));
  else client.on(evt.name, (...args) => evt.execute(...args));
}

client.login(process.env.DISCORD_TOKEN).catch(err => logger.error('Login failed', { err }));
