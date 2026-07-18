const crypto = require('crypto-js');
const secretKey = "special_ç_key";
const signString = "test_sign_string_with_é_special";
const hmac = crypto.HmacSHA512(signString, secretKey);
console.log(crypto.enc.Base64.stringify(hmac));
