"""Cliente de sesiones Django con CSRF, cookies en memoria y verificación de TLS 1.3."""
import http.cookiejar
import json
import ssl
from urllib.parse import urlencode, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, HTTPSHandler, Request

class CloudClient:
    def __init__(self,base_url,username,password,*,allow_local_http=False):
        parsed=urlparse(base_url)
        local=parsed.hostname in ('127.0.0.1','localhost','::1')
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise ValueError('Se requiere una URL base sin credenciales, ruta ni parámetros.')
        if parsed.scheme!='https' and not (parsed.scheme=='http' and local and allow_local_http):
            raise ValueError('Se exige HTTPS. HTTP solo se admite explícitamente en loopback para desarrollo.')
        self.base=base_url.rstrip('/')
        self.username,self.password=username,password
        self.cookies=http.cookiejar.CookieJar()
        context=ssl.create_default_context()
        context.minimum_version=ssl.TLSVersion.TLSv1_3
        context.maximum_version=ssl.TLSVersion.TLSv1_3
        self.opener=build_opener(HTTPSHandler(context=context),HTTPCookieProcessor(self.cookies))
        self.authenticated=False

    def csrf(self):
        return next((cookie.value for cookie in self.cookies if cookie.name=='csrftoken'),'')

    def login(self):
        with self.opener.open(self.base+'/ingresar/',timeout=10) as response: response.read()
        payload=urlencode({'username':self.username,'password':self.password,'csrfmiddlewaretoken':self.csrf()}).encode()
        req=Request(self.base+'/ingresar/',data=payload,headers={'Referer':self.base+'/ingresar/'})
        with self.opener.open(req,timeout=10) as response:
            if '/ingresar/' in response.url: raise PermissionError('Credenciales inválidas.')
            response.read()
        self.authenticated=True

    def send(self,readings):
        if not self.authenticated: self.login()
        req=Request(self.base+'/api/v1/lecturas/lote/',data=json.dumps({'readings':readings}).encode(),headers={'Content-Type':'application/json','X-CSRFToken':self.csrf(),'Referer':self.base+'/conductor/'})
        try:
            with self.opener.open(req,timeout=15) as response:
                if urlparse(response.url).path!='/api/v1/lecturas/lote/': raise PermissionError('La sesión expiró.')
                return json.load(response)
        except Exception:
            self.authenticated=False
            raise
