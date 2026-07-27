import { DataTypes, Model, Sequelize } from 'sequelize';
import type { ProcessingDbModels } from '../index';

export class EventCluster extends Model {
  declare id: string;
  declare time_stamp: Date;
}

export const EventClusterModel = {
  define: (sequelize: Sequelize) => {
    EventCluster.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      time_stamp: {
        type: DataTypes.DATE,
        allowNull: false,
      },
    }, {
      sequelize,
      modelName: 'EventCluster',
      tableName: 'event_cluster',
      timestamps: false,
    });
    return EventCluster;
  },
  createAssociations: (_models: ProcessingDbModels) => {
    // No associations yet
  }
};
