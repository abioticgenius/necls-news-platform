import { Sequelize } from 'sequelize';
import { EventClusterModel } from './models/eventcluster.model';

export type ProcessingDbModels = {
  EventCluster: ReturnType<typeof EventClusterModel.define>;
};

export async function initProcessingDb() {
  console.log('Initializing Processing Database...');
  console.log('Processing DB Config:', {
    host: process.env.PROCESSING_DB_HOST,
    port: process.env.PROCESSING_DB_PORT,
    database: process.env.PROCESSING_DB_NAME,
    user: process.env.PROCESSING_DB_USER
  });
  
  const sequelize = new Sequelize(
    process.env.PROCESSING_DB_NAME!,
    process.env.PROCESSING_DB_USER!,
    process.env.PROCESSING_DB_PASSWORD!,
    {
      host: process.env.PROCESSING_DB_HOST!,
      port: Number(process.env.PROCESSING_DB_PORT!),
      dialect: 'postgres',
      dialectOptions: {
        connectTimeout: 30000,
        ssl: process.env.PROCESSING_DB_HOST?.includes('.rds.amazonaws.com') ? {
          require: true,
          rejectUnauthorized: false,
        } : undefined
      },
      pool: {
        max: 5,
        min: 0,
        acquire: 30000,
        idle: 10000
      }
    }
  );

  console.log('Defining processing models...');
  const models: ProcessingDbModels = {
    EventCluster: EventClusterModel.define(sequelize),
  };

  console.log('Creating processing associations...');
  EventClusterModel.createAssociations(models);

  console.log('Authenticating processing database connection...');
  await sequelize.authenticate();
  console.log('Syncing processing database...');
  await sequelize.sync({ alter: true });
  console.log('Processing Database initialized successfully!');
  return { sequelize, models };
}
