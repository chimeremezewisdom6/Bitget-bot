export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
    if (request.headers.get('X-Webhook-Secret') !== env.WEBHOOK_SECRET) return new Response('Unauthorized', { status: 401 });

    try {
      const { symbol, direction } = await request.json();
      const timestamp = Date.now().toString();
      const path = '/api/v2/mix/order/place-order';
      const side = direction === 'LONG' ? 'buy' : 'sell';
      
      const body = {
        symbol: symbol, productType: 'USDT-FUTURES', marginMode: 'crossed',
        marginCoin: 'USDT', size: '10', side: side, tradeSide: 'open', orderType: 'market'
      };
      const bodyStr = JSON.stringify(body);

      const encoder = new TextEncoder();
      const key = await crypto.subtle.importKey('raw', encoder.encode(env.BITGET_SECRET), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      const signatureBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(timestamp + 'POST' + path + bodyStr));
      const signature = btoa(String.fromCharCode(...new Uint8Array(signatureBuffer)));

      const response = await fetch(`https://api.bitget.com${path}`, {
        method: 'POST',
        headers: {
          'ACCESS-KEY': env.BITGET_API_KEY,
          'ACCESS-SIGN': signature,
          'ACCESS-TIMESTAMP': timestamp,
          'ACCESS-PASSPHRASE': env.BITGET_PASSWORD,
          'Content-Type': 'application/json'
        },
        body: bodyStr
      });

      const result = await response.json();
      return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } });

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500 });
    }
  },
};
