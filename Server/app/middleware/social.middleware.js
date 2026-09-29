import { auth } from "express-openid-connect";

const socialCheck = async (req, res, next) => {
    if (req.body.provider != "local") {
        console.log("Social Account details => ", req.body)
        req.body.isSocial = true;
        next()
    } else {
        req.body.isSocial = false;
        next()
    }
}

export { socialCheck }