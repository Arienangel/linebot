from linebot import WebhookHandler
from linebot.models import MessageEvent


class AsyncWebhookHandler(WebhookHandler):

    def __init__(self, channel_secret):
        super().__init__(channel_secret)

    async def handle(self, body, signature):
        payload = self.parser.parse(body, signature, as_payload=True)
        for event in payload.events:
            func = None
            key = None
            if isinstance(event, MessageEvent):
                key = self.__get_handler_key(event.__class__, event.message.__class__)
                func = self._handlers.get(key, None)
            if func is None:
                key = self.__get_handler_key(event.__class__)
                func = self._handlers.get(key, None)
            if func is None:
                func = self._default
            else:
                await self.__invoke_func(func, event, payload)

    @classmethod
    async def __invoke_func(cls, func, event, payload):
        (has_varargs, args_count) = cls.__get_args_count(func)
        if has_varargs or args_count == 2:
            await func(event, payload.destination)
        elif args_count == 1:
            await func(event)
        else:
            await func()

    @staticmethod
    def __get_args_count(func):
        import inspect
        arg_spec = inspect.getfullargspec(func)
        return (arg_spec.varargs is not None, len(arg_spec.args))

    @staticmethod
    def __get_handler_key(event, message=None):
        if message is None:
            return event.__name__
        else:
            return event.__name__ + '_' + message.__name__
