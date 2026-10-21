export function deploymentSettings(env=process.env){
 const port=Number(env.PORT||4173),publicURL=env.APP_PUBLIC_URL||env.RENDER_EXTERNAL_URL||'',online=!!publicURL;
 if(!Number.isInteger(port)||port<1||port>65535)throw Error('PORT must be between 1 and 65535.');
 const origin=online?new URL(publicURL):new URL('http://127.0.0.1:'+port);
 if(online&&(origin.protocol!=='https:'||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash))throw Error('APP_PUBLIC_URL must be an HTTPS origin without a path or credentials.');
 const host=env.HOST||(online?'0.0.0.0':'127.0.0.1'),adminEmail=String(env.APP_ADMIN_EMAIL||'').trim().toLowerCase(),signupCode=env.APP_SIGNUP_CODE||'';
 if(!online&&!['127.0.0.1','localhost','::1'].includes(host))throw Error('Set APP_PUBLIC_URL and administrator settings before exposing the server.');
 if(online&&(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(adminEmail)||signupCode.length<24))throw Error('Online deployment needs APP_ADMIN_EMAIL and APP_SIGNUP_CODE with at least 24 characters.');
 if(online&&!env.APP_DATA_DIR)throw Error('Online deployment needs APP_DATA_DIR on a persistent local disk.');
 return {port,origin:origin.origin,host,online,adminEmail,signupCode,allowedHosts:new Set([origin.host,`127.0.0.1:${port}`,`localhost:${port}`]),allowedOrigins:new Set(online?[origin.origin]:[origin.origin,`http://localhost:${port}`])};
}
