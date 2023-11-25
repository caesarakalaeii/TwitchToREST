import os
import sys
import threading
import time
sys.path.append('G:/VS_repos/BBR_Twitch_Integrations/TwitchEventsToJSON/python')
from events import *
from logger import Logger
import asyncio
import json
import secrets
from my_secrets import *
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

auth: UserAuthenticator
twitch: Twitch


class Password:
    referral: str
    salt: str
    valid_hash:str
    
    def __init__(self, referral, salt, valid_hash):
        self.referral = referral
        self.salt = salt
        self.valid_hash = valid_hash

class Bot:
    TARGET_SCOPE:[]
    registered_ids: ID_Queue
    passwords:[Password]
    esub: EventSubWebhook
    broadcasters:[Broadcaster]
    
    def __init__(self, app_id, app_secret, endpoint, user_name, server_name, auth_url, webhook_url, webhook_port) -> None:
        self.passwords = []
        self.__app_id = app_id
        self.__app_secret = app_secret
        self.endpoint = endpoint
        self.server_name = server_name
        self.auth_url = auth_url
        self.webhook_url = webhook_url
        self.webhook_port = webhook_port
        self.user_name = user_name
        self.l = Logger(True)
        self.TARGET_SCOPE = [
        AuthScope.MODERATOR_READ_FOLLOWERS,
        AuthScope.CHANNEL_READ_REDEMPTIONS,
        AuthScope.CHANNEL_MANAGE_REDEMPTIONS
        ]
        self.registered_ids = ID_Queue()
        self.broadcasters = []
        self.await_login = True
    
    
    async def register_id(self, steamid):
        '''
        Registeres ID for later check
        '''
        await self.registered_ids.put(steamid)
        
    async def is_id_registered(self, steamid):
        '''
        Check if ID was registered using the proper flow
        '''
        return self.registered_ids.contains(id)
        
    async def resolve_id(self):
        '''
        Return and remove id from queue
        '''
        
        return await self.registered_ids.get()
    
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
    
    async def list_pw_refs(self):
        for p in self.passwords:
            print(p.referral)
        
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

        
        
    async def register_broadcaster(self, caster : Broadcaster):
        d = caster.to_dict()
        d.update({'EventType':'BroadcasterAdd'})
        return await self.REST_post(d)
    
    async def unregister_broadcaster(self, caster : Broadcaster):
        d = caster.to_dict()
        d.update({'EventType':'BroadcasterRemove'})
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
        
        redeems = builder.build(broadcaster_id)
        redeem_ids = {}
        custom_redeem = None
        for redeem in redeems:
            try:
                custom_redeem = await twitch.create_custom_reward(redeem.broadcaster_id, 
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
            except TwitchAPIException as e:
                if e.args[0] == 'Bad Request - CREATE_CUSTOM_REWARD_DUPLICATE_REWARD':
                    self.l.warning(f'Redeem already exists: {e}')
                    #check if broadcaster is known, otherwise raise Exeption
                    await self.load_broadcasters()
                    broadcaster_known = False
                    for caster in self.broadcasters:
                        if redeem.broadcaster_id == caster.id:
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
        await self.esub.listen_channel_follow_v2(broadcaster.id, self.user.id, self.on_follow)
        await self.esub.listen_channel_cheer(broadcaster.id, self.on_cheer)
        for redeem_id in broadcaster.redeem_ids:
            await self.esub.listen_channel_points_custom_reward_redemption_add(broadcaster.id, self.on_redeem, redeem_id)
        await self.esub.listen_channel_subscribe(broadcaster.id, self.on_sub)
        await self.esub.listen_channel_raid(self.on_raid, to_broadcaster_user_id=broadcaster.id)
        await self.esub.listen_channel_subscription_gift(broadcaster.id, self.on_gift)
        await self.esub.listen_channel_subscription_message(broadcaster.id, self.on_sub_message)
        
        
    async def on_follow(self, data: ChannelFollowEvent):
        caster = data.event.broadcaster_user_login
        username = data.event.user_name
        event = Follow(caster, username)
        self.REST_post(event.to_json_dict())
        
    async def on_cheer(self, data: ChannelCheerEvent):
        caster = data.event.broadcaster_user_login
        username = data.event.user_name
        amount = data.event.bits
        message = data.event.message
        event = Bits(caster, username, amount, message)
        self.REST_post(event.to_json_dict())
        
    async def on_redeem(self, data: ChannelPointsCustomRewardRedemptionAddEvent):
        caster = data.event.broadcaster_user_login
        username = data.event.user_name
        redeem_id = data.event.reward.id
        message = data.event.user_input
        event = Redeem(caster, username, redeem_id, message)
        self.REST_post(event.to_json_dict())
        
    async def on_sub(self, data: ChannelSubscribeEvent):
        # ignore gifts as they are handled else where
        if data.event.is_gift:
            return
        caster = data.event.broadcaster_user_login
        username = data.event.user_name
        tier = data.event.tier
        total_time = 1
        streak = 1
        event = Sub(caster, username, tier, total_time, streak)
        self.REST_post(event.to_json_dict())
        
    async def on_sub_message(self, data: ChannelSubscriptionMessageEvent):
        caster = data.event.broadcaster_user_login
        username = data.event.user_name
        tier = data.event.tier
        total_time = data.event.duration_months
        streak = data.event.cumulative_months
        message = data.event.message.text
        event = Sub(caster, username, tier, total_time, streak, message)
        self.REST_post(event.to_json_dict())
        
    async def on_raid(self, data: ChannelRaidEvent):
        caster = data.event.broadcaster_user_login
        username = data.event.user_name
        amount = data.event.viewers
        event = Raid(caster, username, amount)
        self.REST_post(event.to_json_dict())
        
    async def on_gift(self, data: ChannelSubscriptionGiftEvent):
        caster = data.event.broadcaster_user_login
        username = data.event.user_name
        tier = data.event.tier
        amount = data.event.total
        event = SubBomb(caster, username, tier, amount)
        
        self.REST_post(event.to_json_dict())
    
    
    async def add_broadcaster(self, caster: Broadcaster):
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
            
        await self.register_broadcaster(caster)
        
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
        self.broadcasters = [Broadcaster(p['Id'],p['Username'], p['SteamId'], p['RedeemIds']) for p in caster_dicts]
      
      
    async def broadcasters_to_list(self):
        l = []
        for caster in self.broadcasters:
            d = caster.to_dict()
            l.append(d)
        return l    
        
    async def run(self):
        global auth, twitch
        
        if not os.path.exists('data'):
            os.makedirs('data')
        
        await self.load_pws()
        if len(self.passwords) < 1:
            pw = input('Please input a inital password\n')
            ref = 'Admin'
            await bot.add_pw(pw, ref)
        twitch = await Twitch(self.__app_id, self.__app_secret)
        auth = UserAuthenticator(twitch, self.TARGET_SCOPE, url=self.auth_url)
        
        while(self.await_login):
            try:
                self.l.info("App awaiting inital login")
                time.sleep(3)
            except:
                self.l.fail("Keyboard Interrupt, exiting") #not actually working
                raise KeyboardInterrupt("User specified shutdown")
        self.l.passingblue("App inital login successful")
        self.l.passingblue("Welcome home Chief!")
        
        self.esub = EventSubWebhook(self.webhook_url, self.webhook_port, twitch)
        await self.esub.unsubscribe_all() # unsub, other wise stuff breaky
        self.esub.start()
        
        self.user = await first(twitch.get_users(logins=self.user_name))
        await self.load_broadcasters()
        for caster in self.broadcasters:
            await self.initialize_esubs(caster)
            
        self.l.passing('Esubs initialized')
        
bot: Bot      
        
        
        
app = Quart(__name__)


app.secret_key = 'your_secret_key'

    
    
    
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
            await bot.register_id(steam_id)
            return redirect(auth.return_auth_url())
        else:
            return "Invalid username or password. Please try again."

    return await render_template('login.html')


@app.route('/login/confirm')
async def login_confirm():
    global bot, twitch
    args = request.args
    state = request.args.get('state')
    if state != auth.state:
        return 'Bad state', 401
    code = request.args.get('code')
    if code is None:
        return 'Missing code', 400
    try:
        
        token, refresh = await auth.authenticate(user_token=code)
       
        if bot.await_login:
            await twitch.set_user_authentication(token, bot.TARGET_SCOPE, refresh)
            ret_val = "Welcome home chief!"
            
        user_info = await first(twitch.get_users())
        name = user_info.login
        steam_id = await bot.resolve_id()
        
        try:
            redeem_ids = await bot.generate_redeems(user_info.id)
        except FileExistsError as e:
            return f'{e}, please delete the BBR2TTV redeems and try again'
       
        if redeem_ids == None:
            return f'No redeem was initialized, please contact a server admin', 500
            
        if len(redeem_ids) < 1:
            ret_val += f'No redeem was initialized, as they already exists. '
            
        if not bot.await_login:
            await bot.initialize_esubs(user_info.id)
    
        b = Broadcaster(user_info.id, name, steam_id, redeem_ids)
        ret_val += await bot.add_broadcaster(b)
        
        
    except TwitchAPIException as e:
        return 'Failed to generate auth token', 500
    
    bot.await_login = False
    return ret_val

def main():
    asyncio.run(bot.run())
    
    
    


if __name__ == '__main__':
    
    bot = Bot(APP_ID, APP_SECRET, 'http://localhost:5001/api/data', 'caesarlp', 'Test', 'http://localhost:5000/login/confirm','https://webhook.site/71ad5166-1579-46db-a4d4-76c4bff0c062/callback', 5002)
    
    
    process2 = threading.Thread(target=main)

    
    process2.start()
    
    app.run()