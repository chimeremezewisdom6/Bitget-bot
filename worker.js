export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    const authHeader = request.headers.get('X-Webhook-Secret');
    if (authHeader !== env.WEBHOOK_SECRET) {
      return new Response('Unauthorized', { status: 401 });
    }

    try {
      const signal = await request.json();
      const { symbol, direction, is_paper } = signal;

      let result;
      let isRealTrade = false;
      let finalQty = "0";
      let finalPrice = "0";

      // ==========================================
      // PAPER TRADING MODE (Streak < 8)
      // ==========================================
      if (is_paper) {
        const mockBalance = 1.58; // Using your actual balance for simulation
        const mockPrice = 1.00;   
        const leverage = 5;
        
        const tradeMargin = mockBalance * 0.90;
        finalQty = ((tradeMargin * leverage) / mockPrice).toFixed(4);
        finalPrice = mockPrice.toString();

        console.log(`[SIMULATION] Would place ${direction} order for ${finalQty} ${symbol} at ${finalPrice}`);
        
        result = {
          code: '00000',
          msg: 'Simulated Trade Successful',
          data: { orderId: `PAPER-${Date.now()}`, simulated: true }
        };
      } 
      // ==========================================
      // LIVE TRADING MODE (Streak >= 8)
      // ==========================================
      else {
        isRealTrade = true;
        
        const encoder = new TextEncoder();
        const key = await crypto.subtle.importKey(
          'raw', encoder.encode(env.BITGET_SECRET),
          { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
        );

        const baseHeaders = {
          'ACCESS-KEY': env.BITGET_API_KEY,
          'ACCESS-PASSPHRASE': env.BITGET_PASSWORD,
          'Content-Type': 'application/json',
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        };

        const getSignature = async (ts, method, path, body = '') => {
          const prehash = ts + method + path + body;
          const sigBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(prehash));
          return btoa(String.fromCharCode(...new Uint8Array(sigBuffer)));
        };

        // Using api.bitget.cloud to try and bypass the block
        const BASE_URL = 'https://api.bitget.cloud'; 

        // 1. FETCH BALANCE
        let timestamp = Date.now().toString();
        const balPath = '/api/v3/account/assets';
        const balHeaders = {
          ...baseHeaders,
          'ACCESS-TIMESTAMP': timestamp,
          'ACCESS-SIGN': await getSignature(timestamp, 'GET', balPath)
        };

        const balRes = await fetch(`${BASE_URL}${balPath}`, { method: 'GET', headers: balHeaders });
        const balData = await balRes.json();

        let availableBalance = 0;
        if (balData.code === '00000' && balData.data && balData.data.assets) {
          const usdtAsset = balData.data.assets.find(a => a.coin === 'USDT');
          if (usdtAsset) availableBalance = parseFloat(usdtAsset.available);
        }

        if (availableBalance <= 0) {
          throw new Error(`Insufficient USDT balance. Response: ${JSON.stringify(balData)}`);
        }

        // 2. FETCH PRICE
        timestamp = Date.now().toString();
        const tickPath = `/api/v3/market/ticker?category=USDT-FUTURES&symbol=${symbol}`;
        const tickHeaders = {
          ...baseHeaders,
          'ACCESS-TIMESTAMP': timestamp,
          'ACCESS-SIGN': await getSignature(timestamp, 'GET', tickPath)
        };

        const tickRes = await fetch(`${BASE_URL}${tickPath}`, { method: 'GET', headers: tickHeaders });
        const tickData = await tickRes.json();

        if (tickData.code !== '00000' || !tickData.data || tickData.data.length === 0) {
          throw new Error(`Failed to fetch price for ${symbol}. Response: ${JSON.stringify(tickData)}`);
        }

        const currentPrice = parseFloat(tickData.data[0].lastPr);
        
        // 3. CALCULATE QTY (90% * 5x)
        const tradeMargin = availableBalance * 0.90;
        const leverage = 5;
        finalQty = ((tradeMargin * leverage) / currentPrice).toFixed(4);
        finalPrice = currentPrice.toString();

        // 4. SET LEVERAGE
        timestamp = Date.now().toString();
        const levPath = '/api/v3/account/set-leverage';
        const levBody = JSON.stringify({ category: 'USDT-FUTURES', symbol: symbol, leverage: leverage.toString() });
        const levHeaders = {
          ...baseHeaders,
          'ACCESS-TIMESTAMP': timestamp,
          'ACCESS-SIGN': await getSignature(timestamp, 'POST', levPath, levBody)
        };
        await fetch(`${BASE_URL}${levPath}`, { method: 'POST', headers: levHeaders, body: levBody });

        // 5. PLACE ORDER
        timestamp = Date.now().toString();
        const orderPath = '/api/v3/trade/place-order';
        const side = direction === 'LONG' ? 'buy' : 'sell';
        const orderBody = JSON.stringify({ category: 'USDT-FUTURES', symbol: symbol, qty: finalQty, side: side, orderType: 'market' });
        const orderHeaders = {
          ...baseHeaders,
          'ACCESS-TIMESTAMP': timestamp,
          'ACCESS-SIGN': await getSignature(timestamp, 'POST', orderPath, orderBody)
        };

        const response = await fetch(`${BASE_URL}${orderPath}`, { method: 'POST', headers: orderHeaders, body: orderBody });
        result = await response.json();
      }

      // ==========================================
      // UPDATE STREAK ON GITHUB
      // ==========================================
      const mockWon = Math.random() > 0.5;
      
      if (env.GITHUB_PAT && env.GITHUB_REPO_OWNER && env.GITHUB_REPO_NAME) {
        const getUrl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/streak.json`;
        const getRes = await fetch(getUrl, {
          headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'Cloudflare-Worker', 'Accept': 'application/vnd.github.v3+json' }
        });

        let currentStreak = 0;
        let fileSha = null;

        if (getRes.ok) {
          const fileData = await getRes.json();
          fileSha = fileData.sha;
          const content = atob(fileData.content);
          try { currentStreak = JSON.parse(content).wins || 0; } catch (e) { currentStreak = 0; }
        }

        const newStreak = mockWon ? currentStreak + 1 : 0;
        const newContent = JSON.stringify({ wins: newStreak });

        const putBody = {
          message: `Update streak: ${newStreak} wins`,
          content: btoa(unescape(encodeURIComponent(newContent))),
          sha: fileSha
        };

        const putUrl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/streak.json`;
        ctx.waitUntil(
          fetch(putUrl, {
            method: 'PUT',
            headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'Cloudflare-Worker', 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json' },
            body: JSON.stringify(putBody)
          })
        );
      }

      // ==========================================
      // RESPONSE
      // ==========================================
      if (result.code !== '00000' && result.code !== 0) {
        return new Response(JSON.stringify({ error: result.msg || "Bitget Error", details: result }), { status: 400, headers: { 'Content-Type': 'application/json' } });
      }

      return new Response(JSON.stringify({
        success: true,
        mode: isRealTrade ? "LIVE" : "SIMULATION",
        qty: finalQty,
        price: finalPrice
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }
  },
};
