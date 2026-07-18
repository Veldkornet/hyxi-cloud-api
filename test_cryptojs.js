const crypto = require('crypto-js');

const accessKey = "my_ak";
const secretKey = "my_sk";
const path = "/api/token";
const method = "POST";
const timestamp = "1234567890123";
const nonce = "abcdef12";

const contentToHash = "grantType:1";
const hexContentHash = crypto.SHA512(contentToHash).toString(crypto.enc.Hex);

const stringToSign = `${path}\n${method}\n${hexContentHash}\n`;
const signString = `${accessKey}${timestamp}${nonce}${stringToSign}`;

const hmac = crypto.HmacSHA512(signString, secretKey);
const signature = crypto.enc.Base64.stringify(hmac);
console.log("CryptoJS HMAC:", signature);
