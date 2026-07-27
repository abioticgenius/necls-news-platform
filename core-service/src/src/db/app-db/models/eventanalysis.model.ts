import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class EventAnalysis extends Model {
  declare id: string;
  declare event_id: string;
  declare sequence: number;
}

export const EventAnalysisModel = {
  define: (sequelize: Sequelize) => {
    EventAnalysis.init({
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
      modelName: 'EventAnalysis',
      tableName: 'event_analysis',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_id', 'sequence'],
          name: 'uq_event_analysis_event_seq',
        },
      ],
    });
    return EventAnalysis;
  },
  createAssociations: (models: AppDbModels) => {
    EventAnalysis.belongsTo(models.Event, { foreignKey: 'event_id' });
    EventAnalysis.hasMany(models.LocalizedEventAnalysis, { foreignKey: 'event_analysis_id', as: 'LocalizedEventAnalysis' });
  }
};
