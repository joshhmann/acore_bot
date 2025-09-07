import base64
import html
import os
import re
import asyncio
from typing import Optional

import requests


class SoapClient:
    def __init__(self, host: str, port: int, user: Optional[str], password: Optional[str]):
        self.host = host
        self.port = port
        self.user = user or ""
        self.password = password or ""

    def execute(self, command: str, timeout: float = 6.0) -> str:
        url = f"{self._base_url()}"
        envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="urn:AC">
  <SOAP-ENV:Body>
    <ns1:executeCommand>
      <command>{command}</command>
    </ns1:executeCommand>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>'''.encode("utf-8")
        auth = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "Authorization": f"Basic {auth}",
        }
        r = requests.post(url, data=envelope, headers=headers, timeout=timeout)
        r.raise_for_status()
        m = re.search(r"<(?:return|result)[^>]*>(.*?)</(?:return|result)>", r.text, re.S | re.I)
        if m:
            return html.unescape(m.group(1)).strip()
        text = re.sub(r"<[^>]+>", "", r.text)
        return html.unescape(text).strip()

    async def run(self, command: str) -> str:
        return await asyncio.to_thread(self.execute, command)

    def format_error(self, e: Exception) -> str:
        import requests as _req
        if isinstance(e, _req.Timeout):
            return "SOAP request timed out. Check network route and try again."
        if isinstance(e, _req.ConnectionError):
            return f"Cannot connect to SOAP at {self.host}:{self.port}. Verify worldserver is running, host/port, and firewall."
        if isinstance(e, _req.HTTPError):
            resp = e.response
            code = resp.status_code if resp is not None else 'HTTP'
            if resp is not None and code in (401, 403):
                return f"{code} Unauthorized. Check SOAP_USER/SOAP_PASS and worldserver SOAP permissions."
            if resp is not None and code == 404:
                return f"{code} Not Found. Verify SOAP is enabled and the URL {self._base_url()} is correct."
            if resp is not None and code >= 500:
                return f"{code} Server error from worldserver. Check server logs."
            return f"HTTP error {code}."
        return f"Unexpected error: {e}"

    def _base_url(self) -> str:
        return f"http://{self.host}:{self.port}/"

