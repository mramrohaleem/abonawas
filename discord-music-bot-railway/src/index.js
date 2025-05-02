require('dotenv').config()
const fs = require('fs')
const path = require('path')
const { Client, Collection, GatewayIntentBits } = require('discord.js')
const { Player } = require('discord-player')

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildVoiceStates
  ]
})

// In-memory collections
client.commands = new Collection()
client.buttons  = new Collection()
client.embedMessages = new Collection()

// Load slash commands
for (const file of fs.readdirSync(path.join(__dirname, 'commands')).filter(f => f.endsWith('.js'))) {
  const cmd = require(`./commands/${file}`)
  client.commands.set(cmd.data.name, cmd)
}

// Load button handlers
for (const file of fs.readdirSync(path.join(__dirname, 'buttons')).filter(f => f.endsWith('.js'))) {
  const btn = require(`./buttons/${file}`)
  client.buttons.set(btn.customId, btn)
}

// Initialize player
client.player = new Player(client, {
  ytdlOptions: { quality: 'highestaudio', highWaterMark: 1 << 25 }
})

// Register slash commands on ready
client.once('ready', async () => {
  const { REST } = require('@discordjs/rest')
  const { Routes } = require('discord.js')
  const token = process.env.DISCORD_TOKEN
  const clientId = process.env.CLIENT_ID
  const guildId  = process.env.GUILD_ID
  const rest = new REST({ version: '10' }).setToken(token)

  const route = process.env.NODE_ENV === 'production'
    ? Routes.applicationCommands(clientId)
    : Routes.applicationGuildCommands(clientId, guildId)

  await rest.put(route, { body: client.commands.map(c => c.data.toJSON()) })
  console.log(`✅ Logged in as ${client.user.tag}`)
})

// Handle interactions
client.on('interactionCreate', async interaction => {
  try {
    if (interaction.isChatInputCommand()) {
      const cmd = client.commands.get(interaction.commandName)
      if (cmd) await cmd.execute(interaction, client)
    }
    if (interaction.isButton()) {
      const btn = client.buttons.get(interaction.customId)
      if (btn) await btn.execute(interaction, client)
    }
  } catch (err) {
    console.error(err)
    const reply = { content: '❌ An error occurred', ephemeral: true }
    interaction.replied || interaction.deferred
      ? interaction.followUp(reply)
      : interaction.reply(reply)
  }
})

client.login(process.env.DISCORD_TOKEN)