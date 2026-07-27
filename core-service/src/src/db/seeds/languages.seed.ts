import { Language } from '../app-db/models/language.model';

export async function seedLanguages() {
  try {
    console.log('Seeding languages...');
    
    // Check if languages already exist
    const existingLanguages = await Language.findAll();
    if (existingLanguages.length > 0) {
      console.log('Languages already exist, skipping seed');
      return;
    }

    // Insert seed data
    const languages = [
      {
        id: 'en',
        name: 'English'
      },
      {
        id: 'hi',
        name: 'Hindi'
      }
    ];

    await Language.bulkCreate(languages);
    console.log('Successfully seeded languages:', languages.map(l => l.name).join(', '));
    
  } catch (error) {
    console.error('Error seeding languages:', error);
    throw error;
  }
}
