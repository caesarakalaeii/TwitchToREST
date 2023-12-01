import os
import sys
import threading
import time
from events import *
from logger import Logger
import asyncio
import json
import secrets
from some_secrets import *
from config import *
import requests
from redeem_builder import Redeem_Builder, RedeemTemplate
from broadcaster import Broadcaster
from id_queue import ID_Queue
from twitchAPI.helper import first
from quart import Quart, abort, redirect, render_template, request
from passlib.hash import pbkdf2_sha256
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch, TwitchUser
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import ChannelFollowEvent, ChannelSubscribeEvent, ChannelSubscriptionGiftEvent, ChannelSubscriptionMessageEvent, ChannelCheerEvent, ChannelRaidEvent, ChannelPointsCustomRewardRedemptionAddEvent
from twitchAPI.type import AuthScope, ChatEvent, TwitchAPIException, EventSubSubscriptionConflict, EventSubSubscriptionError, EventSubSubscriptionTimeout, TwitchBackendException
from twitchAPI.chat import Chat, EventData, ChatMessage, JoinEvent, JoinedEvent, ChatCommand, ChatUser

from vote import Vote




class Password:
    referral: str
    salt: str
    valid_hash:str
    
    def __init__(self, referral, salt, valid_hash):
        self.referral = referral
        self.salt = salt
        self.valid_hash = valid_hash

class Bot:
    TARGET_SCOPE: []
    twitch: Twitch
    auth: UserAuthenticator
    registered_ids: ID_Queue
    user: TwitchUser
    passwords: [Password]
    esub: EventSubWebhook
    broadcasters: [Broadcaster]
    chat: Chat
    votes: dict
    
    def __init__(self, app_id, app_secret, endpoint, user_name, server_name, auth_url, webhook_url, webhook_port, test = False) -> None:
        self.passwords = []
        self.__app_id = app_id
        self.__app_secret = app_secret
        self.endpoint = endpoint
        self.server_name = server_name
        self.auth_url = auth_url
        self.webhook_url = webhook_url
        self.webhook_port = webhook_port
        self.user_name = user_name
        self.test = test
        self.l = Logger(True)
        self.TARGET_SCOPE = [
        AuthScope.MODERATOR_READ_FOLLOWERS,
        AuthScope.CHANNEL_READ_REDEMPTIONS,
        AuthScope.CHANNEL_MANAGE_REDEMPTIONS,
        AuthScope.BITS_READ,
        AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
        AuthScope.CHAT_READ
        ]
        self.registered_ids = ID_Queue()
        self.broadcasters = []
        self.votes = {}
        self.await_login = True
        self.is_running = True
        self.commands = {
        "help":{
                "help": "help: prints all commands",
                "value": False,
                "cli_func": self.help_cli,
                "permissions": 0
            },
        "stop":{
                "help": "stop: stops the process",
                "value": False,
                "cli_func": self.stop_cli,
                "permissions": 10
        },
        "add_pw":{
            "help": "add_pw [ref]: adds new referral and password",
            "value": True,
            "cli_func": self.add_pw_cli,
            "permissions": 10
            
        },
        "rm_pw":{
            "help": "rm_pw [ref]: removes referral and password",
            "value": True,
            "cli_func": self.rm_pw_cli,
            "permissions": 10
            
        },
        "list_ref":{
            "help": "list_ref: lists all known referrals",
            "value": False,
            "cli_func": self.list_ref_cli,
            "permissions": 10
            
        },
        "rm_caster":{
            "help": "rm_caster [id/name]: removes and unregisteres broadcaster",
            "value": True,
            "cli_func": self.rm_caster_cli,
            "permissions": 10
        }
        ,
        "list_caster":{
            "help": "list_caster: lists all registered broadsasters",
            "value": False,
            "cli_func": self.list_caster_cli,
            "permissions": 10
        },
        "list_caster_ref":{
            "help": "list_caster_ref [ref]: lists all registered broadsasters wich used the referral",
            "value": True,
            "cli_func": self.list_caster_ref_cli,
            "permissions": 10
        }
        
        }
        
        
    async def help_cli(self):
        for command, value in self.commands.items():
            self.l.passing(f'{value["help"]}')
            
    async def stop_cli(self):
        self.l.fail("Stopping!")
        try:
            await self.twitch.close()
        except:
            pass
        self.is_running = False
        raise Exception("Stopped by User") #not the most elegant but works
    
    async def list_ref_cli(self):
        self.l.info('Available Referrals:')
        for p in self.passwords:
            self.l.info(p.referral)
    
    async def add_pw_cli(self, ref:str):
        pw = input('Please input the password:\n')
        
        await self.add_pw(pw, ref)
        self.l.passingblue(f"Password for {ref} was sucessfully created!")
    
    async def rm_pw_cli(self, ref:str):
        await self.remove_pw(ref)
        self.l.warning(f'Password for {ref} was sucessfully removed!')
        
    async def list_caster_cli(self):
        for caster in self.broadcasters:
            self.l.passing(f'Name: {caster.username} ID: {caster.steam_id} SteamID: {caster.steam_id}  Referral: {caster.referral} Redeem_IDs: {caster.redeem_ids}')
        
    async def rm_caster_cli(self, identifier:str):
        if identifier.isdigit():
            await self.remove_broadcaster(caster_id=identifier)
            self.l.warning(f'Bradcaster with ID {identifier} sucessfully removed')
        else:
            await self.remove_broadcaster(caster_name=identifier)
            self.l.warning(f'Bradcaster with name {identifier} sucessfully removed')
    
    async def list_caster_ref_cli(self, ref:str):
        reffed_casts = await self.get_broadcasters_by_ref(ref)
        for caster in reffed_casts:
            self.l.passing(f'Name: {caster.username} ID: {caster.steam_id} SteamID: {caster.steam_id} Referral: {caster.referral} Redeem_IDs: {caster.redeem_ids}')
   
    async def register_id(self, steamid, referral):
        '''
        Registeres ID for later check
        '''
        await self.registered_ids.put(steamid, referral)
        
    async def is_id_registered(self, steamid):
        '''
        Check if ID was registered using the proper flow
        '''
        return self.registered_ids.contains(id)
        
    async def resolve_id(self):
        '''
        Return and remove id from queue
        '''
        ids, ref = await self.registered_ids.get()
        
        return ids, ref
    
    async def add_pw(self, pw:str, referral:str):
        '''
        creates new Password, referral will be used to later revoke permission
        '''
        referral = referral
        salt = secrets.token_hex(32)
        valid_hash = pbkdf2_sha256.hash(pw + salt)
        p = Password(referral, salt, valid_hash)
        self.passwords.append(p)
        
        await self.update_pws()
        
    async def remove_pw(self, referral:str):
        '''
        removes password by referral
        '''
        for p in self.passwords:
            if referral == p.referral:
                self.passwords.remove(p)
        
        await self.update_pws()
        
    async def update_pws(self):
        # Convert Password objects to dictionaries
        password_dicts = [{'referral': p.referral, 'salt': p.salt, 'valid_hash': p.valid_hash} for p in self.passwords]

        # Save the array of dictionaries to a JSON file
        with open('data/pws.json', 'w') as file:
            json.dump(password_dicts, file)

    async def load_pws(self):
        # Check if the file exists, create it if not
        file_path = 'data/pws.json'
        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                json.dump([], file)

        # Load the array of dictionaries from the JSON file
        with open(file_path, 'r') as file:
            password_dicts = json.load(file)

        # Convert dictionaries back to Password objects
        self.passwords = [Password(p['referral'], p['salt'], p['valid_hash']) for p in password_dicts]

    async def find_caster(self, twitch_id:str = None, twitch_login:str = None, steam_id:str = None):
        for caster in self.broadcasters:
            if twitch_id == caster.twitch_id:
                return caster
            if twitch_login == caster.twitch_login:
                return caster
            if steam_id == caster.steam_id:
                return caster
        return None
       
    async def register_broadcaster(self, steam_id:str):
        caster:Broadcaster = await self.find_caster(steam_id = steam_id)
        d = caster.to_dict(False)
        d.update({'EventType':'AddBroadcaster'})
        if not steam_id in self.votes.keys():
            self.votes[caster.steam_id] = Vote(caster, self.l, self.endpoint)
        return await self.REST_post(d)
    
    async def unregister_broadcaster(self, caster : Broadcaster):
        d = caster.to_dict(False)
        self.votes.pop(caster.steam_id)
        d.update({'EventType':'RemoveBroadcaster'})
        return await self.REST_post(d)
            
    async def REST_post(self, data:dict):
    
        """
        Send a JSON POST request to a specified endpoint.

        Parameters:
        - data (dict): The JSON data to be sent in the request payload.

        Returns:
        - dict: The JSON response from the server.
        """
        
        
        # Convert the data to JSON format
        json_data = json.dumps(data)

        self.l.info(f'Data ready to send: {json_data}')
        

        # Make the POST request
        response = requests.post(self.endpoint, json=json_data)

        # Check if the request was successful (status code 2xx)
        if response.ok:
            return f'Sucessfully registered at {self.server_name}'
        else:
            # If the request was unsuccessful, raise an exception with the error message
            response.raise_for_status()
            return f'Error registering at {self.server_name}'
        
    async def generate_redeems(self, broadcaster_id):
        builder = Redeem_Builder()
        self.l.info("Generating Redeems")
        redeems = builder.build(broadcaster_id)
        redeem_ids = {}
        custom_redeem = None
        for redeem in redeems:
            try:
                self.l.info(f"Generating redeem: {redeem.title}")
                custom_redeem = await self.twitch.create_custom_reward(redeem.broadcaster_id, 
                                                                    redeem.title, 
                                                                    redeem.cost, 
                                                                    redeem.prompt, 
                                                                    redeem.is_enabled, 
                                                                    redeem.background_color, 
                                                                    redeem.is_user_input_required, 
                                                                    redeem.is_max_per_stream_enabled, 
                                                                    redeem.max_per_stream, 
                                                                    redeem.is_max_per_user_per_stream_enabled, 
                                                                    redeem.max_per_user_per_stream, 
                                                                    redeem.is_global_cooldown_enabled, 
                                                                    redeem.global_cooldown_seconds, 
                                                                    redeem.should_redemptions_skip_request_queue)
                redeem_ids.update({redeem.redeem_type:custom_redeem.id})
                await asyncio.sleep(0.1)
            except TwitchAPIException as e:
                if e.args[0] == 'Bad Request - CREATE_CUSTOM_REWARD_DUPLICATE_REWARD':
                    self.l.warning(f'Redeem already exists: {e}')
                    #check if broadcaster is known, otherwise raise Exeption
                    await self.load_broadcasters()
                    broadcaster_known = False
                    for caster in self.broadcasters:
                        if redeem.broadcaster_id == caster.twitch_id:
                            broadcaster_known = True
                            break
                    if not broadcaster_known:
                        raise FileExistsError('Redeem already exists, but Broadcaster is not known')
                    
                else:
                    self.l.error(f'There was an error during Redeem-Creation: {e}')
            except Exception as e:
                self.l.error(f'There was an error during Redeem-Creation: {e}')
        return redeem_ids
    
    async def initialize_esubs(self, broadcaster : Broadcaster):
        if self.test:
                self.l.warning('Skipping Esub init! Test flag is set!')
                return
        await self.esub.listen_channel_follow_v2(broadcaster.twitch_id, self.user.id, self.on_follow)
        await self.esub.listen_channel_cheer(broadcaster.twitch_id, self.on_cheer)
        for redeem_id in broadcaster.redeem_ids.values():
            await self.esub.listen_channel_points_custom_reward_redemption_add(broadcaster.twitch_id, self.on_redeem, redeem_id)
        await self.esub.listen_channel_subscribe(broadcaster.twitch_id, self.on_sub)
        await self.esub.listen_channel_raid(self.on_raid, to_broadcaster_user_id=broadcaster.twitch_id)
        await self.esub.listen_channel_subscription_gift(broadcaster.twitch_id, self.on_gift)
        await self.esub.listen_channel_subscription_message(broadcaster.twitch_id, self.on_sub_message)
     
    async def on_follow(self, data: ChannelFollowEvent):
        caster: Broadcaster = await self.find_caster(twitch_login=data.event.broadcaster_user_login)
        username = data.event.user_name
        event = Follow(caster.twitch_login, username, caster.steam_id)
        await self.REST_post(event.to_json_dict())
        
    async def on_cheer(self, data: ChannelCheerEvent):
        caster: Broadcaster = await self.find_caster(twitch_login=data.event.broadcaster_user_login)
        username = data.event.user_name
        amount = data.event.bits
        message = data.event.message
        event = Bits(caster.twitch_login, username, caster.steam_id, amount, message)
        await self.REST_post(event.to_json_dict())
        
    async def on_redeem(self, data: ChannelPointsCustomRewardRedemptionAddEvent):
        caster: Broadcaster = await self.find_caster(twitch_login=data.event.broadcaster_user_login)
        username = data.event.user_name
        redeem_id = data.event.reward.id
        redeem_type = None
        for k,v in caster.redeem_ids.items():
            if v == redeem_id:
                redeem_type = k
                break
        
        message = data.event.user_input
        if redeem_type == 'test':
            for k,v in caster.redeem_ids.items():
                if k == 'test':
                    continue
                try:
                    event = Redeem(caster.twitch_login, username, caster.steam_id, k, message)
                    await self.REST_post(event.to_json_dict())
                    await asyncio.sleep(10)
                except ValueError as e:
                    self.l.error(e)
                    pass
                    
            return
                
        
        
        try:
            event = Redeem(caster.twitch_login, username, caster.steam_id, redeem_type, message)
            await self.REST_post(event.to_json_dict())
        except ValueError as e:
            self.l.error(e)
            pass
        
    async def on_sub(self, data: ChannelSubscribeEvent):
        # ignore gifts as they are handled else where
        if data.event.is_gift:
            return
        caster: Broadcaster = await self.find_caster(twitch_login=data.event.broadcaster_user_login)
        username = data.event.user_name
        tier = data.event.tier
        total_time = 1
        streak = 1
        event = Sub(caster.twitch_login, username, caster.steam_id, tier, total_time, streak)
        await self.REST_post(event.to_json_dict())
        
    async def on_sub_message(self, data: ChannelSubscriptionMessageEvent):
        caster: Broadcaster = await self.find_caster(twitch_login=data.event.broadcaster_user_login)
        username = data.event.user_name
        tier = data.event.tier
        total_time = data.event.duration_months
        streak = data.event.cumulative_months
        message = data.event.message.text
        event = Sub(caster.twitch_login, username, caster.steam_id, tier, total_time, streak, message)
        await self.REST_post(event.to_json_dict())
        
    async def on_raid(self, data: ChannelRaidEvent):
        caster: Broadcaster = await self.find_caster(twitch_login=data.event.to_broadcaster_user_login)
        username = data.event.from_broadcaster_user_login
        amount = data.event.viewers
        event = Raid(caster.twitch_login, username, caster.steam_id, amount)
        await self.REST_post(event.to_json_dict())
        
    async def on_gift(self, data: ChannelSubscriptionGiftEvent):
        caster: Broadcaster = await self.find_caster(twitch_login=data.event.broadcaster_user_login)
        username = data.event.user_name
        tier = data.event.tier
        amount = data.event.total
        event = SubBomb(caster.twitch_login, username, caster.steam_id, tier, amount)
        
        await self.REST_post(event.to_json_dict())
    
    async def on_message_typed(self, data:ChatMessage):
        choice = 0
        if data.text == "1":
            choice = 1
        if data.text == "2":
            choice = 2
        if data.text == "3":
            choice = 3
        if data.text == "4":
            choice = 4
        if choice != 0:
            self.l.info(f"Choice from {data.user.display_name} is {choice}")
            caster: Broadcaster = await self.find_caster(twitch_id=data.room)
            self.l.info(f"Room is {data.room}, Caster ID is {caster.steam_id}")
            self.l.info(f"K:{self.votes.keys()} V:{self.votes.items()}")
            
            vote: Vote = self.votes[caster.steam_id]
            if vote.vote_on_going and not data.user.id in vote.voted:
                self.l.info(f"Choice will be registered")
                vote.voted.append(data.user.id)
                vote.register_vote(choice)
                
    
    async def remove_broadcaster(self, caster_name:str = None, caster_id:str = None):
        for caster in self.broadcasters:
            if caster_name == caster.twitch_login or caster_id == caster.steam_id:
                self.broadcasters.remove(caster)
        try:
            self.add_broadcaster(self.broadcasters[0])
        except IndexError:
            pass
  
    async def add_broadcaster(self, caster: Broadcaster):
        known = False
        for c in self.broadcasters:
            if caster.twitch_id == c.twitch_id:
                known = True
                c.redeem_ids.update(caster.redeem_ids)
                break
        if not known:
            self.broadcasters.append(caster)
        
        file_path = 'data/broadcasters.json'
        
        # Check if the file exists
        if not os.path.exists(file_path):
            # If the file doesn't exist, create it
            with open(file_path, 'x') as file:
                json.dump([], file) # Initialize with an empty list
        
        # Now open the file and write the updated data
        with open(file_path, 'w') as file:
            json.dump(await self.broadcasters_to_list(), file)
            
        try:
            await self.register_broadcaster(caster.steam_id)
        except:
            return f'Server {self.server_name} is unresponsive, please try again later or contact an admin'
        
        await self.chat.join_room(caster.twitch_login)
        
        return f'Sucessfully registered at {self.server_name}'
   
    async def load_broadcasters(self):
        file_path = 'data/broadcasters.json'
        
        if not os.path.exists(file_path):
            # If the file doesn't exist, create it
            with open(file_path, 'x') as file:
                json.dump([], file) # Initialize with an empty list
        
        with open(file_path, 'r') as file:
            caster_dicts = json.load(file)
        

        # Convert dictionaries back to Password objects
        self.broadcasters = [Broadcaster(p['TwitchId'],p['TwitchLogin'], p['SteamId'], p['RedeemIds'], p['Referral']) for p in caster_dicts]
      
    async def broadcasters_to_list(self):
        l = []
        for caster in self.broadcasters:
            d = caster.to_dict()
            l.append(d)
        return l    
        
    async def get_broadcasters_by_ref(self, ref:str):
        reffed_casters =[]
        for caster in self.broadcasters:
            if caster.referral == ref:
                reffed_casters.append(caster)
                
        return reffed_casters
    
    async def on_ready(self,ready_event: EventData):
        caster_logins = []
        for caster in self.broadcasters:
            caster_logins.append(caster.twitch_login)
            self.votes[caster.steam_id] = Vote(caster, self.l, self.endpoint)
        await self.chat.join_room(caster_logins)
    
    async def run(self):
        
        if not os.path.exists('data'):
            os.makedirs('data')
        
        await self.load_pws()
        if len(self.passwords) < 1:
            pw = input('Please input a inital password\n')
            ref = 'Admin'
            await bot.add_pw(pw, ref)
        self.twitch = await Twitch(self.__app_id, self.__app_secret)
        self.auth = UserAuthenticator(self.twitch, self.TARGET_SCOPE, url=self.auth_url)
        while(self.await_login):
            try:
                self.l.info("App awaiting inital login")
                time.sleep(1)
            except:
                self.l.fail("Keyboard Interrupt, exiting") #not actually working
                raise KeyboardInterrupt("User specified shutdown")
        self.l.passingblue("App inital login successful")
        self.l.passingblue("Welcome home Chief!")
        self.user = await first(self.twitch.get_users(logins=self.user_name))
        
        self.esub = EventSubWebhook(self.webhook_url, self.webhook_port, self.twitch)
        await self.esub.unsubscribe_all() # unsub, other wise stuff breaky
        self.esub.start()
        
        self.chat = await Chat(self.twitch)
        self.chat.register_event(ChatEvent.MESSAGE, self.on_message_typed)
        self.chat.register_event(ChatEvent.READY, self.on_ready)
        
        self.chat.start()
        
        await self.load_broadcasters()
        
        for caster in self.broadcasters:
            if self.test:
                self.l.warning('Skipping Esub and chat init! Test flag is set!')
                break
            await self.initialize_esubs(caster)
            
            
        self.l.passing('Esubs initialized')
        
        self.l.passing('Starting CLI')
        
        await self.cli()
        
    async def cli(self):
        while(self.is_running):
            try:
                com = input("type help for available commands\n")
                await self.command_handler(com)
            except Exception as e:
                self.l.error(f'Exeption in cli_run, exiting: {e}')
                exit(1)
                
    async def command_handler(self, command :str):
        parts = command.split(" ")
        if parts[0] == '':
            return
        if not(parts[0] in self.commands.keys()):
            self.l.error(f'Command {parts[0]} unknown')
        if self.commands[parts[0]]['value']:
           await self.commands[parts[0]]['cli_func'](parts[1])
           return
        await self.commands[parts[0]]['cli_func']()
            
    async def init_vote(self, steam_id: str):
        if self.votes[steam_id].isRunning:
            self.l.info(f'Vote Already started a thread, restarting')
            self.votes[steam_id].isRunning = False
            await self.init_vote(steam_id)
            return
        
        self.l.info(f'Starting new Vote thread')
        self.votes[steam_id].isRunning = True
        loop_task = asyncio.create_task(self.votes[steam_id].vote())
        
    async def start_vote(self, steam_id: str):
        if self.votes[steam_id].vote_on_going:
            self.l.info(f'Vote Already on going')
            return
        if not self.votes[steam_id].isRunning:
            self.l.info(f'Vote not running, starting')
            await self.init_vote(steam_id)
        self.votes[steam_id].vote_on_going = True
        
    async def stop_vote(self, steam_id:str):
        self.votes[steam_id].isRunning = False
        
        
        
bot = Bot(APP_ID, APP_SECRET, f'http://{REST_URI}:{REST_PORT}/api/data', USER_NAME, SERVER_NAME, AUTH_URL,WEBHOOK_URL, WEBHOOK_PORT, TEST)
     
        
        
        
app = Quart(__name__)


app.secret_key = 'your_secret_key'

    
@app.route('/privacy')
async def privacy():
    return await render_template('privacy.html')
    
@app.route('/bbr', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        data = await request.form
        steam_id:str = data['steam_id']
        ref:str = data['referral']
        password:str = data['password']
        
        valid_salt, valid_password_hash = None, None
        
        for pw in bot.passwords:
            if pw.referral.lower() == ref.lower():
                valid_salt = pw.salt
                valid_password_hash = pw.valid_hash
        
        if valid_salt == None:
            return "Invalid username or password. Please try again."

        if steam_id.isdigit() and pbkdf2_sha256.verify(password + valid_salt, valid_password_hash):
            await bot.register_id(steam_id, ref)
            return redirect(bot.auth.return_auth_url())
        else:
            return "Invalid username or password. Please try again."

    return await render_template('login.html')

@app.route('/vote', methods=['POST'])
async def receive_vote():
    try:
        data = await request.get_json()
        # Assuming the incoming data is in JSON format
        bot.l.info(f'Got Data for vote {data}')
        
        if data["Vote"] == "Init":
            await bot.init_vote(data["SteamId"])
        if data["Vote"] == "Start":
            await bot.start_vote(data["SteamId"])
        if data["Vote"] == "Stop":
            await bot.stop_vote(data["SteamId"])
        # Handle the data as needed

        return "Data received successfully", 200
    except Exception as e:
        print("Error processing the request:", str(e))
        return "Error processing the request", 500

@app.route('/login/confirm')
async def login_confirm():
    args = request.args
    state = request.args.get('state')
    ret_val = ''
    await_login = bot.await_login
    if state != bot.auth.state:
        return 'Bad state', 401
    code = request.args.get('code')
    if code is None:
        return 'Missing code', 400
    try:
        
        token, refresh = await bot.auth.authenticate(user_token=code)
       
        if await_login:
            await bot.twitch.set_user_authentication(token, bot.TARGET_SCOPE, refresh)
            ret_val += "Welcome home chief! "
            bot.await_login = False
            await asyncio.sleep(5) #wait for initial init
            
        user_info = await first(bot.twitch.get_users())
        name = user_info.login
        steam_id, referral = await bot.resolve_id()
        
        try:
            redeem_ids = await bot.generate_redeems(user_info.id)
        except FileExistsError as e:
            return f'{e}, please delete the TTV2BBR redeems and try again'
       
        if redeem_ids == None:
            return f' No redeem was initialized, please contact a server admin', 500
            
        if len(redeem_ids) < 1:
            ret_val += f' No redeem was initialized, as they already exist. '
            
        if not await_login:
            caster = await bot.find_caster(twitch_id=user_info.id)
            await bot.initialize_esubs(caster)
    
        
        b = Broadcaster(user_info.id, name, steam_id, redeem_ids, referral)
        ret_val += await bot.add_broadcaster(b)
        
        
    except TwitchAPIException as e:
        return 'Failed to generate auth token', 500
    
    
    return ret_val

def main():
    asyncio.run(bot.run())
    
    
    


if __name__ == '__main__':
    
    
    
    process2 = threading.Thread(target=main)

    
    process2.start()
    
    app.run(host='0.0.0.0',port = AUTH_PORT)