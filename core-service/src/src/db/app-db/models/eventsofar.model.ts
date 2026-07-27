import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class EventSoFar extends Model {
  declare id: string;
  declare event_id: string;
  declare sequence: number;
}

export const EventSoFarModel = {
  define: (sequelize: Sequelize) => {
    EventSoFar.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      event_id: {
        type: DataTypes.UUID,
        allowNull: false,
        references: {
          model: 'event',
          key: 'id',
        },
        onDelete: 'CASCADE',
      },
      sequence: {
        type: DataTypes.INTEGER,
        allowNull: false,
      },
    }, {
      sequelize,
      modelName: 'EventSoFar',
      tableName: 'event_so_far',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_id', 'sequence'],
          name: 'uq_event_so_far_event_seq',
        },
      ],
    });
    return EventSoFar;
  },
  createAssociations: (models: AppDbModels) => {
    EventSoFar.belongsTo(models.Event, { foreignKey: 'event_id' });
    EventSoFar.hasMany(models.LocalizedEventSoFar, { foreignKey: 'event_so_far_id', as: 'LocalizedEventSoFar' });
  }
};
