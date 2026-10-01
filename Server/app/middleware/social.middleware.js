import { auth } from "express-openid-connect";

const socialCheck = async (req, res, next) => {
    if (req.body.provider != "local") {
        console.log("Social sign-in:", req.body?.provider)
        req.body.isSocial = true;
        next()
    } else {
        req.body.isSocial = false;
        next()
    }
}

export { socialCheck }