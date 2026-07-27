import { seedLanguages } from './languages.seed';
import { seedImagePlaceholderPatterns } from './image-placeholder-patterns.seed';

export async function runSeeds() {
  try {
    console.log('Starting database seeding...');
    
    // Run language seeds
    await seedLanguages();
    
    // Run image placeholder pattern seeds
    await seedImagePlaceholderPatterns();
    
    console.log('Database seeding completed successfully!');
  } catch (error) {
    console.error('Error during seeding:', error);
    throw error;
  }
}
