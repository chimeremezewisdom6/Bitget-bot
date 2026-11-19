export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
    const authHeader = request.headers.get('X-Webhook-Secret');
    if (authHeader !== env.WEBHOOK_SECRET) return new Response('Unauthorized', { status: 401 });

    try {
      const signal = await request.json();
      
      const getGithubFile = async (filename) => {
        const gurl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/${filename}`;
        const res = await fetch(gurl, {
          headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'CF-Worker', 'Accept': 'application/vnd.github.v3+json' }
        });
        if (!res.ok) return null;
        const data = await res.json();
        return { sha: data.sha, content: JSON.parse(atob(data.content)) };
      };

      const updateGithubFile = async (filename, content, sha) => {
        const gurl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/contents/${filename}`;
        await fetch(gurl, {
          method: 'PUT',
          headers: { 'Authorization': `token ${env.GITHUB_PAT}`, 'User-Agent': 'CF-Worker', 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json' },
          body: JSON.stringify({ message: `Update ${filename}`, content: btoa(JSON.stringify(content)), sha: sha })
        });
      };

      const getPrice = async (sym) => {
        const res = await fetch(`https://api.bitget.com/api/v2/mix/market/ticker?symbol=${sym}&productType=USDT-FUTURES`);
        const data = await res.json();
        if (data.code === '00000' && data.data && data.data.length > 0) {
            return parseFloat(data.data[0].lastPr);
        }
        throw new Error(`Failed to get price for ${sym}. Bitget might be blocking Cloudflare IP.`);
      };

      const tradeState = await getGithubFile('active_trade.json');
      const streakState = await getGithubFile('streak.json');
      
      let activeTrade = tradeState ? tradeState.content : { active: false };
      let currentStreak = streakState ? streakState.content.wins : 0;
      let isLiveMode = currentStreak >= 8;

      if (activeTrade.active) {
        const currentPrice = await getPrice(activeTrade.symbol);
        let pnlPercent = 0;
        
        if (activeTrade.direction === 'LONG') {
          pnlPercent = ((currentPrice - activeTrade.entry_price) / activeTrade.entry_price) * 100;
        } else {
          pnlPercent = ((activeTrade.entry_price - currentPrice) / activeTrade.entry_price) * 100;
        }

        let peakPnl = activeTrade.peak_pnl || 0;
        if (pnlPercent > peakPnl) peakPnl = pnlPercent;

        let hitTP = false;
        let hitSL = false;

        if (activeTrade.direction === 'LONG') {
            if (currentPrice >= activeTrade.take_profit) hitTP = true;
            if (currentPrice <= activeTrade.stop_loss) hitSL = true;
        } else {
            if (currentPrice <= activeTrade.take_profit) hitTP = true;
            if (currentPrice >= activeTrade.stop_loss) hitSL = true;
        }

        const isFading = peakPnl > 0.3 && pnlPercent < (peakPnl - 0.2) && pnlPercent > 0;

        if (hitTP || hitSL || isFading) {
          const won = pnlPercent > 0;
          currentStreak = won ? currentStreak + 1 : 0;
          
          let reason = hitTP ? "TAKE PROFIT" : hitSL ? "STOP LOSS" : "TRAILING STOP";

          await updateGithubFile('streak.json', { wins: currentStreak }, streakState.sha);
          await updateGithubFile('active_trade.json', { active: false }, tradeState.sha);

          return new Response(JSON.stringify({ 
            status: "CLOSED", symbol: activeTrade.symbol, direction: activeTrade.direction,
            pnl_percent: pnlPercent.toFixed(2), peak_pnl: peakPnl.toFixed(2),
            reason: reason, won: won, streak: currentStreak 
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        } else {
          activeTrade.peak_pnl = peakPnl;
          await updateGithubFile('active_trade.json', activeTrade, tradeState.sha);

          return new Response(JSON.stringify({ 
            status: "HOLDING", symbol: activeTrade.symbol, direction: activeTrade.direction,
            pnl_percent: pnlPercent.toFixed(2), peak_pnl: peakPnl.toFixed(2)
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
      } 
      else {
        if (signal.symbol === "NONE") {
          return new Response(JSON.stringify({ status: "WAITING", message: "No signal found." }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        // 🚨 USE THE PRICE PASSED FROM PYTHON INSTEAD OF FETCHING 🚨
        const currentPrice = signal.current_price || await getPrice(signal.symbol); 
        
        let take_profit, stop_loss;
        if (signal.direction === 'LONG') {
            stop_loss = signal.low_15m * 0.999;
            take_profit = signal.high_15m * 1.002;
        } else {
            stop_loss = signal.high_15m * 1.001;
            take_profit = signal.low_15m * 0.998;
        }

        const newTrade = {
          active: true, 
          symbol: signal.symbol, 
          direction: signal.direction,
          entry_price: currentPrice, 
          take_profit: take_profit,
          stop_loss: stop_loss,
          peak_pnl: 0, 
          opened_at: Date.now()
        };

        await updateGithubFile('active_trade.json', newTrade, tradeState.sha);

        return new Response(JSON.stringify({ 
          status: "OPENED", symbol: signal.symbol, direction: signal.direction,
          entry_price: currentPrice.toFixed(5), take_profit: take_profit.toFixed(5), stop_loss: stop_loss.toFixed(5),
          mode: isLiveMode ? "LIVE" : "PAPER"
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }
  },
};
