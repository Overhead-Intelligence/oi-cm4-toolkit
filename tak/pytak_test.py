from configparser import ConfigParser
import pytak
import asyncio

async def main():
    cfg = ConfigParser()
    cfg.add_section("tak_tls")

    # 1) Tell PyTAK to use TLS on port 8443:
    cfg.set("tak_tls", "COT_URL", "tls://10.224.5.255:8089")

    # 2) Point to your client cert, key, and CA bundle:
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_CERT", r"C:\Users\jean\OneDrive\Documents\Code Projects\oi-cm4-toolkit\tak\certs\client_cert.pem")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_KEY",  r"C:\Users\jean\OneDrive\Documents\Code Projects\oi-cm4-toolkit\tak\certs\client_key.pem")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_CAFILE",r"C:\Users\jean\OneDrive\Documents\Code Projects\oi-cm4-toolkit\tak\certs\ca_bundle.pem")

    # 3) (Optional) For testing only—disable server cert or hostname checks:
    cfg.set("tak_tls", "PYTAK_TLS_DONT_VERIFY",       "1")
    cfg.set("tak_tls", "PYTAK_TLS_DONT_CHECK_HOSTNAME","1")

    # 4) Pick a stable UID for your client:
    cfg.set("tak_tls", "COT_HOST_ID", "cm4-tls-client")

    conf = cfg["tak_tls"]

    # This will under the covers call create_tls_client() from client_functions.py
    reader, writer = await pytak.protocol_factory(conf)
    
    # Now send your CoT location as before...
    cot = pytak.gen_cot(lat=27.95391667, lon=-81.61530556, hae=10.0,
                       uid=conf["COT_HOST_ID"], cot_type="a-f-A-U-A")
    # writer is an asyncio StreamWriter over TLS:
    writer.write(cot)
    await writer.drain()

    # When you're done:
    writer.close()
    await writer.wait_closed()

if __name__=="__main__":
    asyncio.run(main())
