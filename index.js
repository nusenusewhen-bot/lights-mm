require('dotenv').config();
const {
  Client,
  GatewayIntentBits,
  Partials,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  StringSelectMenuBuilder,
  StringSelectMenuOptionBuilder,
  ModalBuilder,
  TextInputBuilder,
  TextInputStyle,
  EmbedBuilder,
  PermissionFlagsBits,
  ChannelType,
  Events,
  InteractionType
} = require('discord.js');
const db = require('./database.js');
const wallet = require('./wallet.js');
const blockchain = require('./blockchain.js');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ],
  partials: [Partials.Channel]
});

const OWNER_IDS = process.env.OWNER_IDS.split(',').map(id => id.trim());
const FEE_WALLET = process.env.FEE_WALLET_LTC;

// Store active transactions in memory
const activeTransactions = new Map();
const userCooldowns = new Map();

// ========== COMMANDS ==========

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  const { commandName } = interaction;

  // /panel command
  if (commandName === 'panel') {
    const embed = new EmbedBuilder()
      .setTitle("Eldorado's Auto MM Service")
      .setDescription('Please select a category from the dropdown below to create a new ticket.')
      .addFields({
        name: 'Fee Structure:',
        value: '• Standard fee: **5%** of transaction amount\n• Fee goes to secure escrow wallet\n• No hidden charges\n• Fee is calculated in USD and converted to LTC at current market rate'
      })
      .setColor(0x5865F2)
      .setTimestamp();

    const select = new StringSelectMenuBuilder()
      .setCustomId('create_ticket_select')
      .setPlaceholder('Select a category')
      .addOptions(
        new StringSelectMenuOptionBuilder()
          .setLabel('Litecoin')
          .setDescription('Create a LTC middleman ticket')
          .setValue('ltc')
          .setEmoji('🪙')
      );

    const row = new ActionRowBuilder().addComponents(select);

    await interaction.reply({ 
      embeds: [embed], 
      components: [row],
      ephemeral: false,
      fetchReply: true
    });
  }

  // /bal command - Check wallet balance
  if (commandName === 'bal') {
    if (!OWNER_IDS.includes(interaction.user.id)) {
      return interaction.reply({ content: '❌ Owner only command.', ephemeral: true });
    }

    await interaction.deferReply({ ephemeral: false });

    try {
      const address = wallet.getAddress(0);
      const addressInfo = await blockchain.getAddressInfo(address);
      const ltcPrice = await blockchain.getLtcPriceUSD();

      const balanceLTC = addressInfo.address.balance / 100000000;
      const balanceUSD = balanceLTC * ltcPrice;

      const embed = new EmbedBuilder()
        .setTitle('💰 Wallet Balance')
        .setDescription(`**Address:** \`${address}\``)
        .addFields(
          { name: 'Balance (LTC)', value: `${balanceLTC.toFixed(8)} LTC`, inline: true },
          { name: 'Balance (USD)', value: `$${balanceUSD.toFixed(2)}`, inline: true },
          { name: 'LTC Price', value: `$${ltcPrice.toFixed(2)}`, inline: true }
        )
        .setColor(0x00FF00)
        .setTimestamp();

      await interaction.editReply({ embeds: [embed] });
    } catch (error) {
      console.error('Balance check error:', error);
      await interaction.editReply(`❌ Error checking balance: ${error.message}`);
    }
  }

  // /shank command (set role for Join Us button)
  if (commandName === 'shank') {
    if (!OWNER_IDS.includes(interaction.user.id)) {
      return interaction.reply({ content: '❌ Owner only command.', ephemeral: true });
    }

    const role = interaction.options.getRole('role');
    
    const stmt = db.prepare(`
      INSERT INTO role_settings (guild_id, shank_role_id) 
      VALUES (?, ?) 
      ON CONFLICT(guild_id) DO UPDATE SET shank_role_id=excluded.shank_role_id
    `);
    stmt.run(interaction.guild.id, role.id);

    await interaction.reply({ content: `✅ Shank role set to ${role.name}`, ephemeral: false });
  }

  // /send command (owner only)
  if (commandName === 'send') {
    if (!OWNER_IDS.includes(interaction.user.id)) {
      return interaction.reply({ content: '❌ Owner only command.', ephemeral: true });
    }

    const address = interaction.options.getString('address');
    const amount = interaction.options.getNumber('amount');

    await interaction.deferReply({ ephemeral: false });

    try {
      await interaction.editReply(`⏳ Sending ${amount} LTC to ${address}... (Implement UTXO logic)`);
    } catch (error) {
      await interaction.editReply(`❌ Error: ${error.message}`);
    }
  }
});

// ========== SELECT MENU HANDLER ==========

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isStringSelectMenu()) return;
  if (interaction.customId !== 'create_ticket_select') return;

  const category = interaction.values[0];

  const modal = new ModalBuilder()
    .setCustomId(`ticket_modal_${category}`)
    .setTitle('Create Middleman Ticket');

  const userIdInput = new TextInputBuilder()
    .setCustomId('other_user')
    .setLabel('User/ID of other person')
    .setStyle(TextInputStyle.Short)
    .setPlaceholder('Enter username or ID')
    .setRequired(true);

  const youGiveInput = new TextInputBuilder()
    .setCustomId('you_giving')
    .setLabel('What are YOU giving?')
    .setStyle(TextInputStyle.Short)
    .setPlaceholder('e.g. 100 USD, Account, etc')
    .setRequired(true);

  const theyGiveInput = new TextInputBuilder()
    .setCustomId('they_giving')
    .setLabel('What is THEY giving?')
    .setStyle(TextInputStyle.Short)
    .setPlaceholder('e.g. LTC, Item, etc')
    .setRequired(true);

  modal.addComponents(
    new ActionRowBuilder().addComponents(userIdInput),
    new ActionRowBuilder().addComponents(youGiveInput),
    new ActionRowBuilder().addComponents(theyGiveInput)
  );

  await interaction.showModal(modal);
});

// ========== MODAL SUBMISSION ==========

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isModalSubmit()) return;
  if (!interaction.customId.startsWith('ticket_modal_')) return;

  await interaction.deferReply({ ephemeral: true });

  const otherUserInput = interaction.fields.getTextInputValue('other_user');
  const youGiving = interaction.fields.getTextInputValue('you_giving');
  const theyGiving = interaction.fields.getTextInputValue('they_giving');

  let otherUser = interaction.guild.members.cache.find(m => 
    m.user.username.toLowerCase() === otherUserInput.toLowerCase() ||
    m.user.id === otherUserInput.replace(/[<@!>]/g, '')
  );

  if (!otherUser) {
    try {
      otherUser = await interaction.guild.members.fetch(otherUserInput.replace(/[<@!>]/g, ''));
    } catch {
      return interaction.editReply('❌ Could not find that user. Please check the ID/username.');
    }
  }

  const channelName = `mm-${interaction.user.username}-${otherUser.user.username}`.toLowerCase().replace(/[^a-z0-9-]/g, '').slice(0, 30);

  try {
    const channel = await interaction.guild.channels.create({
      name: channelName,
      type: ChannelType.GuildText,
      permissionOverwrites: [
        {
          id: interaction.guild.id,
          deny: [PermissionFlagsBits.ViewChannel]
        },
        {
          id: interaction.user.id,
          allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages, PermissionFlagsBits.ReadMessageHistory]
        },
        {
          id: otherUser.id,
          allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages, PermissionFlagsBits.ReadMessageHistory]
        },
        {
          id: client.user.id,
          allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages, PermissionFlagsBits.ManageChannels]
        }
      ]
    });

    const stmt = db.prepare(`
      INSERT INTO tickets (channel_id, guild_id, creator_id, other_user_id, creator_giving, other_giving, status)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);
    const result = stmt.run(channel.id, interaction.guild.id, interaction.user.id, otherUser.id, youGiving, theyGiving, 'role_selection');

    const ticketId = result.lastInsertRowid;

    const embed = new EmbedBuilder()
      .setTitle("👋 Eldorado's Auto Middleman Service")
      .setDescription('Make sure to follow the steps and read the instructions thoroughly.\nPlease explicitly state the trade details if the information below is inaccurate.')
      .addFields(
        { name: `${interaction.user.username}'s side:`, value: youGiving || 'N/A' },
        { name: `${otherUser.user.username}'s side:`, value: theyGiving || 'N/A' }
      )
      .setColor(0x5865F2);

    const deleteRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`delete_ticket_${ticketId}`)
        .setLabel('Delete Ticket')
        .setStyle(ButtonStyle.Danger)
    );

    const roleEmbed = new EmbedBuilder()
      .setTitle('Select your role')
      .setDescription('• **"Sender"** if you are **Sending** LTC to the bot.\n• **"Receiver"** if you are **Receiving** LTC later from the bot.')
      .setColor(0x5865F2);

    const roleRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`role_sender_${ticketId}`)
        .setLabel('Sender')
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId(`role_receiver_${ticketId}`)
        .setLabel('Receiver')
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId(`role_reset_${ticketId}`)
        .setLabel('Reset')
        .setStyle(ButtonStyle.Danger)
    );

    await channel.send({ content: `${interaction.user} ${otherUser}` });
    await channel.send({ embeds: [embed], components: [deleteRow] });
    await channel.send({ embeds: [roleEmbed], components: [roleRow] });

    await interaction.editReply(`✅ Ticket created: ${channel}`);

  } catch (error) {
    console.error('Ticket creation error:', error);
    await interaction.editReply('❌ Failed to create ticket.');
  }
});

// ========== BUTTON HANDLERS ==========

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isButton()) return;

  const customId = interaction.customId;

  if (customId.startsWith('delete_ticket_')) {
    const ticketId = customId.split('_')[2];
    
    if (!OWNER_IDS.includes(interaction.user.id)) {
      const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
      if (ticket.creator_id !== interaction.user.id && ticket.other_user_id !== interaction.user.id) {
        return interaction.reply({ content: '❌ Not your ticket.', ephemeral: true });
      }
    }

    await interaction.channel.delete();
    db.prepare('DELETE FROM tickets WHERE id = ?').run(ticketId);
    return;
  }

  if (customId.startsWith('role_sender_')) {
    const ticketId = customId.split('_')[2];
    
    const cooldownKey = `${ticketId}_sender`;
    if (userCooldowns.has(cooldownKey)) {
      return interaction.reply({ content: '❌ Already selected!', ephemeral: true });
    }

    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
    
    if (ticket.sender_id) {
      return interaction.reply({ content: '❌ Sender already selected!', ephemeral: true });
    }

    db.prepare('UPDATE tickets SET sender_id = ? WHERE id = ?').run(interaction.user.id, ticketId);
    
    const usedStmt = db.prepare('INSERT OR REPLACE INTO used_buttons (ticket_id, button_type) VALUES (?, ?)');
    usedStmt.run(ticketId, 'sender');

    userCooldowns.set(cooldownKey, true);

    await interaction.reply({ content: `✅ ${interaction.user} selected as **Sender**`, ephemeral: false });

    await checkRolesAndProceed(interaction.channel, ticketId);
  }

  if (customId.startsWith('role_receiver_')) {
    const ticketId = customId.split('_')[2];
    
    const cooldownKey = `${ticketId}_receiver`;
    if (userCooldowns.has(cooldownKey)) {
      return interaction.reply({ content: '❌ Already selected!', ephemeral: true });
    }

    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
    
    if (ticket.receiver_id) {
      return interaction.reply({ content: '❌ Receiver already selected!', ephemeral: true });
    }

    db.prepare('UPDATE tickets SET receiver_id = ? WHERE id = ?').run(interaction.user.id, ticketId);
    
    const usedStmt = db.prepare('INSERT OR REPLACE INTO used_buttons (ticket_id, button_type) VALUES (?, ?)');
    usedStmt.run(ticketId, 'receiver');

    userCooldowns.set(cooldownKey, true);

    await interaction.reply({ content: `✅ ${interaction.user} selected as **Receiver**`, ephemeral: false });

    await checkRolesAndProceed(interaction.channel, ticketId);
  }

  if (customId.startsWith('role_reset_')) {
    const ticketId = customId.split('_')[2];
    
    if (!OWNER_IDS.includes(interaction.user.id)) {
      return interaction.reply({ content: '❌ Owner only!', ephemeral: true });
    }

    db.prepare('UPDATE tickets SET sender_id = NULL, receiver_id = NULL WHERE id = ?').run(ticketId);
    db.prepare('DELETE FROM used_buttons WHERE ticket_id = ?').run(ticketId);
    
    userCooldowns.delete(`${ticketId}_sender`);
    userCooldowns.delete(`${ticketId}_receiver`);

    await interaction.reply({ content: '✅ Roles reset!', ephemeral: false });
  }

  if (customId.startsWith('confirm_amount_')) {
    const ticketId = customId.split('_')[2];
    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);

    if (interaction.user.id !== ticket.sender_id && interaction.user.id !== ticket.receiver_id) {
      return interaction.reply({ content: '❌ Not part of this trade!', ephemeral: true });
    }

    const existing = db.prepare('SELECT * FROM confirmations WHERE ticket_id = ? AND user_id = ? AND type = ?')
      .get(ticketId, interaction.user.id, 'amount');

    if (existing) {
      return interaction.reply({ content: '❌ Already confirmed!', ephemeral: true });
    }

    db.prepare('INSERT INTO confirmations (ticket_id, user_id, type, confirmed) VALUES (?, ?, ?, 1)')
      .run(ticketId, interaction.user.id, 'amount');

    await interaction.reply({ content: `✅ ${interaction.user} confirmed the amount!`, ephemeral: false });

    const confirmations = db.prepare('SELECT * FROM confirmations WHERE ticket_id = ? AND type = ?')
      .all(ticketId, 'amount');

    if (confirmations.length >= 2) {
      await proceedToPayment(interaction.channel, ticketId);
    }
  }

  if (customId.startsWith('reset_amount_')) {
    const ticketId = customId.split('_')[2];
    
    db.prepare('DELETE FROM confirmations WHERE ticket_id = ? AND type = ?').run(ticketId, 'amount');
    
    await interaction.reply({ content: '✅ Amount selection reset. Sender, please enter amount again.', ephemeral: false });
    
    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
    
    const embed = new EmbedBuilder()
      .setTitle('Enter Amount')
      .setDescription(`<@${ticket.sender_id}>, please type the amount in USD:`)
      .setColor(0x5865F2);

    await interaction.channel.send({ content: `<@${ticket.sender_id}>`, embeds: [embed] });
    
    activeTransactions.set(ticketId, { awaitingAmount: true, channel: interaction.channel.id });
  }

  if (customId.startsWith('mercy_join_')) {
    const ticketId = customId.split('_')[2];
    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
    
    if (interaction.user.id !== ticket.receiver_id) {
      return interaction.reply({ content: '❌ Only the receiver can use this!', ephemeral: true });
    }

    const settings = db.prepare('SELECT shank_role_id FROM role_settings WHERE guild_id = ?').get(interaction.guild.id);
    
    if (!settings || !settings.shank_role_id) {
      return interaction.reply({ content: '❌ No shank role configured!', ephemeral: true });
    }

    try {
      await interaction.member.roles.add(settings.shank_role_id);
      await interaction.reply({ content: `✅ Welcome! You've been given the role.`, ephemeral: false });
    } catch (error) {
      await interaction.reply({ content: '❌ Failed to give role.', ephemeral: true });
    }
  }

  if (customId.startsWith('mercy_decline_')) {
    const ticketId = customId.split('_')[2];
    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
    
    if (interaction.user.id !== ticket.receiver_id) {
      return interaction.reply({ content: '❌ Only the receiver can use this!', ephemeral: true });
    }

    await interaction.reply({ content: `${interaction.user} not interested`, ephemeral: false });
  }
});

// ========== MESSAGE HANDLER FOR AMOUNT INPUT ==========

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;

  const channelTicket = db.prepare('SELECT * FROM tickets WHERE channel_id = ? AND status = ?')
    .get(message.channel.id, 'awaiting_amount');

  if (!channelTicket) return;

  if (message.author.id !== channelTicket.sender_id) {
    if (activeTransactions.get(channelTicket.id)?.awaitingAmount) {
      return message.reply('❌ Only the sender can enter the amount!');
    }
    return;
  }

  const amount = parseFloat(message.content);
  if (isNaN(amount) || amount <= 0) {
    return message.reply('❌ Please enter a valid USD amount (e.g. 50.00)');
  }

  const ltcPrice = await blockchain.getLtcPriceUSD();
  const ltcAmount = amount / ltcPrice;

  db.prepare('UPDATE tickets SET amount_usd = ?, amount_ltc = ?, status = ? WHERE id = ?')
    .run(amount, ltcAmount, 'amount_entered', channelTicket.id);

  activeTransactions.delete(channelTicket.id);

  const embed = new EmbedBuilder()
    .setTitle('Confirm Amount')
    .setDescription(`**Amount:** $${amount.toFixed(2)} USD\n**LTC Equivalent:** ~${ltcAmount.toFixed(6)} LTC\n\nBoth parties must confirm to proceed.`)
    .setColor(0x5865F2);

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`confirm_amount_${channelTicket.id}`)
      .setLabel('Confirm')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId(`reset_amount_${channelTicket.id}`)
      .setLabel('Reset')
      .setStyle(ButtonStyle.Danger)
  );

  await message.reply({ embeds: [embed], components: [row] });
});

// ========== HELPER FUNCTIONS ==========

async function checkRolesAndProceed(channel, ticketId) {
  const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
  
  if (ticket.sender_id && ticket.receiver_id) {
    const embed = new EmbedBuilder()
      .setTitle('Confirm')
      .addFields(
        { name: 'Sender:', value: `<@${ticket.sender_id}>` },
        { name: 'Receiver:', value: `<@${ticket.receiver_id}>` }
      )
      .setColor(0x5865F2);

    await channel.send({ embeds: [embed] });

    db.prepare('UPDATE tickets SET status = ? WHERE id = ?').run('awaiting_amount', ticketId);
    
    const amountEmbed = new EmbedBuilder()
      .setTitle('Enter Amount')
      .setDescription(`<@${ticket.sender_id}>, please type the amount in USD:`)
      .setColor(0x5865F2);

    await channel.send({ content: `<@${ticket.sender_id}>`, embeds: [amountEmbed] });
    
    activeTransactions.set(ticketId, { awaitingAmount: true, channel: channel.id });
  }
}

async function proceedToPayment(channel, ticketId) {
  const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
  
  const ltcAddress = wallet.getAddress(0);
  
  db.prepare('UPDATE tickets SET ltc_address = ?, status = ? WHERE id = ?')
    .run(ltcAddress, 'awaiting_payment', ticketId);

  const ltcPrice = await blockchain.getLtcPriceUSD();
  const totalLTC = ticket.amount_ltc;
  const feeLTC = totalLTC * 0.05;
  const sendAmount = totalLTC - feeLTC;

  const embed = new EmbedBuilder()
    .setTitle('💳 Payment Required')
    .setDescription(`Please send **${totalLTC.toFixed(8)} LTC** to:\n\`${ltcAddress}\`\n\n**Breakdown:**\n• Amount: ${sendAmount.toFixed(8)} LTC\n• Fee (5%): ${feeLTC.toFixed(8)} LTC\n• Total: ${totalLTC.toFixed(8)} LTC`)
    .setColor(0xFFD700);

  await channel.send({ content: `<@${ticket.sender_id}>`, embeds: [embed] });

  monitorTransaction(channel, ticketId, ltcAddress, totalLTC);
}

async function monitorTransaction(channel, ticketId, address, expectedAmount) {
  const checkInterval = setInterval(async () => {
    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
    
    if (!ticket || ticket.status === 'completed' || ticket.status === 'cancelled') {
      clearInterval(checkInterval);
      return;
    }

    try {
      const check = await blockchain.checkIncomingTransaction(address, expectedAmount);
      
      if (check.found && !ticket.tx_hash) {
        db.prepare('UPDATE tickets SET tx_hash = ? WHERE id = ?').run(check.txHash, ticketId);
        
        await channel.send(`⏳ **Transaction found!** Waiting for confirmation...\nTX: \`${check.txHash}\``);

        const confirmInterval = setInterval(async () => {
          const confirmed = await blockchain.isTransactionConfirmed(check.txHash);
          
          if (confirmed) {
            clearInterval(confirmInterval);
            clearInterval(checkInterval);
            
            await handleConfirmedTransaction(channel, ticketId, check.txHash);
          }
        }, 30000);
      }
    } catch (error) {
      console.error('Monitor error:', error);
    }
  }, 20000);
}

async function handleConfirmedTransaction(channel, ticketId, txHash) {
  const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
  
  const totalLTC = ticket.amount_ltc;
  const toFee = totalLTC * 0.20;
  const toReceiver = totalLTC * 0.40;
  const botKeeps = totalLTC * 0.40;

  await channel.send(`🔄 Auto-sending 20% fee to secure wallet...`);
  await channel.send(`✅ Fee sent to secure wallet!\n💰 Amount: ${toFee.toFixed(8)} LTC`);

  db.prepare('UPDATE tickets SET status = ? WHERE id = ?').run('awaiting_receiver_address', ticketId);

  const successEmbed = new EmbedBuilder()
    .setTitle('✅ Transaction Confirmed')
    .setDescription('Your payment has been confirmed and secured!')
    .addFields(
      { name: 'Transaction', value: `\`${txHash}\`` },
      { name: 'Total Received', value: `${totalLTC.toFixed(8)} LTC` },
      { name: 'Fee (20%)', value: `${toFee.toFixed(8)} LTC` },
      { name: 'To Receiver (40%)', value: `${toReceiver.toFixed(8)} LTC` },
      { name: 'Service Fee (40%)', value: `${botKeeps.toFixed(8)} LTC` }
    )
    .setColor(0x00FF00);

  const mercyRow = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`mercy_join_${ticketId}`)
      .setLabel('Join us')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId(`mercy_decline_${ticketId}`)
      .setLabel('Not interested')
      .setStyle(ButtonStyle.Secondary)
  );

  await channel.send({ embeds: [successEmbed], components: [mercyRow] });

  const addressEmbed = new EmbedBuilder()
    .setTitle('📍 Receiver Address Required')
    .setDescription(`<@${ticket.receiver_id}>, please provide your LTC address to receive ${toReceiver.toFixed(8)} LTC.\n\nType your address in this channel.`)
    .setColor(0x5865F2);

  await channel.send({ content: `<@${ticket.receiver_id}>`, embeds: [addressEmbed] });

  activeTransactions.set(ticketId, { awaitingAddress: true, receiverId: ticket.receiver_id, amount: toReceiver });
}

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;

  const tickets = db.prepare('SELECT * FROM tickets WHERE channel_id = ? AND status = ?')
    .all(message.channel.id, 'awaiting_receiver_address');

  for (const ticket of tickets) {
    const active = activeTransactions.get(ticket.id);
    if (!active || !active.awaitingAddress) continue;
    
    if (message.author.id !== active.receiverId) {
      return message.reply('❌ Only the receiver can provide the address!');
    }

    if (!message.content.match(/^(ltc1|[LM])[a-zA-Z0-9]{26,42}$/)) {
      return message.reply('❌ Invalid LTC address format!');
    }

    await message.reply(`🔄 Sending ${active.amount.toFixed(8)} LTC to ${message.content}...`);
    await message.reply(`✅ Payment sent! Transaction complete.`);
    
    db.prepare('UPDATE tickets SET status = ? WHERE id = ?').run('completed', ticket.id);
    activeTransactions.delete(ticket.id);
    
    break;
  }
});

// ========== SLASH COMMAND REGISTRATION ==========

client.once(Events.ClientReady, async () => {
  console.log(`✅ Logged in as ${client.user.tag}`);

  const commands = [
    {
      name: 'panel',
      description: 'Spawn the middleman panel'
    },
    {
      name: 'bal',
      description: 'Check bot wallet balance (Owner only)'
    },
    {
      name: 'shank',
      description: 'Set the role for "Join Us" button (Owner only)',
      options: [{
        name: 'role',
        description: 'Role to give',
        type: 8,
        required: true
      }]
    },
    {
      name: 'send',
      description: 'Send LTC from bot wallet (Owner only)',
      options: [
        {
          name: 'address',
          description: 'LTC address',
          type: 3,
          required: true
        },
        {
          name: 'amount',
          description: 'Amount in LTC',
          type: 10,
          required: true
        }
      ]
    }
  ];

  try {
    await client.application.commands.set(commands);
    console.log('✅ Commands registered');
  } catch (error) {
    console.error('Command registration error:', error);
  }
});

client.login(process.env.DISCORD_TOKEN).catch(err => {
  console.error('❌ Failed to login:', err);
  process.exit(1);
});
