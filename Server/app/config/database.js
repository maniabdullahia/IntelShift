import mongoose from "mongoose";

const connectDB = async () => {
    try {
        const MONGO_URI = process.env.MONGO_URI ;
        if (!MONGO_URI) {
            throw new Error('MONGO_URI is not defined in environment variables');
        }
        const connection = await mongoose.connect(MONGO_URI);
        console.log(`Connected to MongoDB ${connection.connection.name}`);

    } catch (error) {
        console.error(`[DATABASE CONNECTION ERROR] ${error.message}`);
    }
}

export default connectDB;
