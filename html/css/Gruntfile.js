module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-less');
  require('jit-grunt')(grunt);

  grunt.initConfig({
    less: {
      development: {
        options: {
          compress: false, // change this when going to production
          yuicompress: false, // change this when going to production
          optimization: 2
        },
        files: {
          "main.css": "less/main.less" // destination file and source file
        }
      }
    },
    watch: {
      styles: {
        files: ['less/*.less'], // which files to watch
        tasks: ['less'],
        options: {
          nospawn: true
        }
      }
    }
  });

  grunt.registerTask('default', ['less', 'watch']);
};