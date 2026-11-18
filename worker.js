export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    // 1. Security Check
    const authHeader = request.headers.get('X-Webhook-Secret');
    if (authHeader !== env.WEBHOOK_SECRET) {
      return new Response('Unauthorized', { status: 401 });
    }

    try {
      const signal = await request.json();
      const { symbol, direction, is_paper } = signal;
      
      const encoder = new TextEncoder();
      const key = await crypto.subtle.importKey(
        'raw', encoder.encode(env.BITGET_SECRET),
        { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
      );

      // Base Headers for all requests
      const baseHeaders = {
        'ACCESS-KEY': env.BITGET_API_KEY,
        'ACCESS-PASSPHRASE': env.BITGET_PASSWORD,
        'Content-Type': 'application/json'
      };

      if (is_paper) {
        baseHeaders['paptrading'] = '1'; // Paper Trading Header
      }

      // Helper function to generate signatures
      const getSignature = async (ts, method, path, body = '') => {
        const prehash = ts + method + path + body;
        const sigBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(prehash));
        return btoa(String.fromCharCode(...new Uint8Array(sigBuffer)));
      };

      // ==========================================
      // STEP 2: FETCH ACCOUNT BALANCE
      // ==========================================
      let timestamp = Date.now().toString();
      const balPath = '/api/v3/account/assets';
      const balHeaders = {
        ...baseHeaders,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-SIGN': await getSignature(timestamp, 'GET', balPath)
      };

      const balRes = await fetch(`https://api.bitget.com${balPath}`, { method: 'GET', headers: balHeaders });
      const balData = await balRes.json();
      
      let availableBalance = 0;
      if (balData.code === '00000' && balData.data) {
        // Find USDT balance
        const usdtAsset = balData.data.find(a => a.coin === 'USDT');
        if (usdtAsset) {
          availableBalance = parseFloat(usdtAsset.available);
        }
      }

      if (availableBalance <= 0) {
        throw new Error("Insufficient USDT balance or failed to fetch balance.");
      }

      // ==========================================
      // STEP 3: FETCH CURRENT PRICE
      // ==========================================
      timestamp = Date.now().toString();
      const tickPath = `/api/v3/market/ticker?category=USDT-FUTURES&symbol=${symbol}`;
      const tickHeaders = {
        ...baseHeaders,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-SIGN': await getSignature(timestamp, 'GET', tickPath)
      };

      const tickRes = await fetch(`https://api.bitget.com${tickPath}`, { method: 'GET', headers: tickHeaders });
      const tickData = await tickRes.json();

      if (tickData.code !== '00000' || !tickData.data || tickData.data.length === 0) {
        throw new Error(`Failed to fetch price for ${symbol}`);
      }

      const currentPrice = parseFloat(tickData.data[0].lastPr);

      // ==========================================
      // STEP 4: CALCULATE QUANTITY (90% Balance * 5x)
      // ==========================================
      const tradeMargin = availableBalance * 0.90; // 90% of balance
      const leverage = 5;
      const totalPositionValue = tradeMargin * leverage;
      
      let rawQty = totalPositionValue / currentPrice;
      
      // Round to 4 decimal places
      let qtyStr = rawQty.toFixed(4); 

      // ==========================================
      // STEP 5: SET LEVERAGE TO 5x
      // ==========================================
      timestamp = Date.now().toString();
      const levPath = '/api/v3/account/set-leverage';
      const levBody = JSON.stringify({
        category: 'USDT-FUTURES',
        symbol: symbol,
        leverage: leverage.toString()
      });
      const levHeaders = {
        ...baseHeaders,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-SIGN': await getSignature(timestamp, 'POST', levPath, levBody)
      };

      await fetch(`https://api.bitget.com${levPath}`, { method: 'POST', headers: levHeaders, body: levBody });

      // ==========================================
      // STEP 6: PLACE ORDER
      // ==========================================
      timestamp = Date.now().toString();
      const orderPath = '/api/v3/trade/place-order';
      const side = direction === 'LONG' ? 'buy' : 'sell';
      
      const orderBody = JSON.stringify({
        category: 'USDT-FUTURES',
        symbol: symbol,
        qty: qtyStr,
        side: side,
        orderType: 'market'
      });

      const orderHeaders = {
        ...baseHeaders,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-SIGN': await getSignature(timestamp, 'POST', orderPath, orderBody)
      };

      const response = await fetch(`https://api.bitget.com${orderPath}`, {
        method: 'POST', headers: orderHeaders, body: orderBody
      });

      const result = await response.json();

      // ==========================================
      // STEP 7: REPORT TO HUGGING FACE
      // ==========================================
      if (env.HF_SPACE_URL) {
        const mockWon = Math.random() > 0.5; // Simulate 50% win rate for paper trading
        ctx.waitUntil(
          fetch(`${env.HF_SPACE_URL}/trade_result`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Webhook-Secret': env.WEBHOOK_SECRET,
            },
            body: JSON.stringify({ won: mockWon }),
          })
        );
      }

      if (result.code !== '00000' && result.code !== 0) {
        return new Response(JSON.stringify({ error: result.msg || "Bitget Error", details: result }), {
          status: 400, headers: { 'Content-Type': 'application/json' },
        });
      }

      return new Response(JSON.stringify({ 
        success: true, 
        balance_used: tradeMargin.toFixed(2), 
        qty: qtyStr, 
        price: currentPrice 
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500, headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};
